import asyncio
import logging
import httpx
import paramiko
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from database import SessionLocal
from models import ManagedApp, AppStatus, Incident, AlertLog
from notifier import send_alert_email, send_recovery_email
from config import settings

logger = logging.getLogger(__name__)

# Global reference to broadcast function (set from main.py)
broadcast_fn = None


async def check_app_health(app: ManagedApp) -> bool:
    """Try to reach the app's health endpoint. Returns True if alive."""
    url = app.url.rstrip("/") + app.health_path
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.get(url)
            return resp.status_code < 500
    except Exception:
        return False


async def run_health_checks():
    """Main loop: check all enabled apps every CHECK_INTERVAL_SECONDS."""
    logger.info("Health monitor started (interval=%ds)", settings.CHECK_INTERVAL_SECONDS)
    while True:
        try:
            await _do_checks()
        except Exception as e:
            logger.error("Health check cycle error: %s", e)
        await asyncio.sleep(settings.CHECK_INTERVAL_SECONDS)


async def _do_checks():
    db: Session = SessionLocal()
    try:
        apps = db.query(ManagedApp).filter(ManagedApp.enabled == True).all()
        for app in apps:
            is_up = await check_app_health(app)
            now = datetime.utcnow()
            prev_status = app.status

            if is_up:
                # Was it down before? Create resolved incident.
                if app.down_since is not None:
                    open_incident = db.query(Incident).filter(
                        Incident.app_id == app.id,
                        Incident.resolved_at == None
                    ).first()
                    if open_incident:
                        open_incident.resolved_at = now
                        open_incident.duration_seconds = int((now - open_incident.started_at).total_seconds())
                    
                    # Send recovery email
                    if app.alert_sent:
                        success = send_recovery_email(app.name, app.url, app.down_since)
                        db.add(AlertLog(
                            app_id=app.id,
                            alert_type="recovery_email",
                            message=f"Recovery after {int((now - app.down_since).total_seconds() / 60)}m",
                            success=success
                        ))

                app.status = AppStatus.ONLINE
                app.last_seen_online = now
                app.down_since = None
                app.alert_sent = False
            else:
                if app.down_since is None:
                    app.down_since = now
                    # Open a new incident
                    db.add(Incident(app_id=app.id, started_at=now))

                # Check if we need to send an alert
                down_duration = now - app.down_since
                threshold = timedelta(minutes=settings.DOWN_ALERT_MINUTES)
                if down_duration >= threshold and not app.alert_sent:
                    success = send_alert_email(app.name, app.url, app.down_since)
                    app.alert_sent = True
                    db.add(AlertLog(
                        app_id=app.id,
                        alert_type="downtime_email",
                        message=f"App down for {int(down_duration.total_seconds() / 60)} minutes",
                        success=success
                    ))

                app.status = AppStatus.OFFLINE

            app.last_checked = now
            db.commit()

            # Broadcast status change via WebSocket
            if broadcast_fn and prev_status != app.status:
                await broadcast_fn({
                    "event": "status_change",
                    "app_id": app.id,
                    "app_name": app.name,
                    "status": app.status.value,
                    "down_since": app.down_since.isoformat() if app.down_since else None,
                })
    finally:
        db.close()


# ─── SSH Command Execution ───────────────────────────────────────────────────

def ssh_exec(app: ManagedApp, command: str) -> tuple[bool, str]:
    """Execute a command via SSH on the remote host. Returns (success, output)."""
    if not app.ssh_host or not command:
        return False, "SSH host or command not configured."

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        connect_kwargs = {
            "hostname": app.ssh_host,
            "port": app.ssh_port or 22,
            "username": app.ssh_user or "root",
            "timeout": 30,
        }
        if app.ssh_key_path:
            connect_kwargs["key_filename"] = app.ssh_key_path
        
        client.connect(**connect_kwargs)
        stdin, stdout, stderr = client.exec_command(command, timeout=60)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        exit_code = stdout.channel.recv_exit_status()
        output = (out + err).strip()
        return exit_code == 0, output
    except Exception as e:
        return False, str(e)
    finally:
        client.close()
