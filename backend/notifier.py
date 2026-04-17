import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone
from config import settings

logger = logging.getLogger(__name__)


def send_alert_email(app_name: str, app_url: str, down_since: datetime) -> bool:
    """Send downtime alert email. Returns True if sent successfully."""
    if not all([settings.SMTP_USER, settings.SMTP_PASSWORD, settings.ALERT_TO]):
        logger.warning("Email not configured — skipping alert for %s", app_name)
        return False

    duration = datetime.utcnow() - down_since.replace(tzinfo=None) if down_since.tzinfo else datetime.utcnow() - down_since
    duration_min = int(duration.total_seconds() / 60)

    subject = f"🔴 ALERT: {app_name} is DOWN ({duration_min}m)"
    body_html = f"""
    <html><body style="font-family:monospace;background:#0d0d0d;color:#e0e0e0;padding:24px;">
      <div style="border:1px solid #ff3b3b;padding:20px;max-width:600px;">
        <h2 style="color:#ff3b3b;margin:0 0 16px;">⚠ DOWNTIME ALERT</h2>
        <table style="width:100%;border-collapse:collapse;">
          <tr><td style="color:#888;padding:6px 0;">Application</td><td style="color:#fff;font-weight:bold;">{app_name}</td></tr>
          <tr><td style="color:#888;padding:6px 0;">URL</td><td style="color:#f0a500;">{app_url}</td></tr>
          <tr><td style="color:#888;padding:6px 0;">Down since</td><td>{down_since.strftime('%Y-%m-%d %H:%M:%S UTC')}</td></tr>
          <tr><td style="color:#888;padding:6px 0;">Duration</td><td style="color:#ff3b3b;">{duration_min} minutes</td></tr>
        </table>
        <p style="margin-top:16px;color:#888;font-size:12px;">Sent by AppCTL Monitor</p>
      </div>
    </body></html>
    """

    recipients = [r.strip() for r in settings.ALERT_TO.split(",") if r.strip()]
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.ALERT_FROM or settings.SMTP_USER
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(body_html, "html"))

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(msg["From"], recipients, msg.as_string())
        logger.info("Alert email sent for %s", app_name)
        return True
    except Exception as e:
        logger.error("Failed to send alert email for %s: %s", app_name, e)
        return False


def send_recovery_email(app_name: str, app_url: str, down_since: datetime) -> bool:
    """Send recovery notification email."""
    if not all([settings.SMTP_USER, settings.SMTP_PASSWORD, settings.ALERT_TO]):
        return False

    duration = datetime.utcnow() - down_since.replace(tzinfo=None) if down_since.tzinfo else datetime.utcnow() - down_since
    duration_min = int(duration.total_seconds() / 60)

    subject = f"✅ RECOVERED: {app_name} is back online"
    body_html = f"""
    <html><body style="font-family:monospace;background:#0d0d0d;color:#e0e0e0;padding:24px;">
      <div style="border:1px solid #00ff88;padding:20px;max-width:600px;">
        <h2 style="color:#00ff88;margin:0 0 16px;">✓ SERVICE RECOVERED</h2>
        <table style="width:100%;border-collapse:collapse;">
          <tr><td style="color:#888;padding:6px 0;">Application</td><td style="color:#fff;font-weight:bold;">{app_name}</td></tr>
          <tr><td style="color:#888;padding:6px 0;">URL</td><td style="color:#f0a500;">{app_url}</td></tr>
          <tr><td style="color:#888;padding:6px 0;">Total downtime</td><td style="color:#00ff88;">{duration_min} minutes</td></tr>
        </table>
        <p style="margin-top:16px;color:#888;font-size:12px;">Sent by AppCTL Monitor</p>
      </div>
    </body></html>
    """

    recipients = [r.strip() for r in settings.ALERT_TO.split(",") if r.strip()]
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.ALERT_FROM or settings.SMTP_USER
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(body_html, "html"))

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(msg["From"], recipients, msg.as_string())
        logger.info("Recovery email sent for %s", app_name)
        return True
    except Exception as e:
        logger.error("Failed to send recovery email for %s: %s", app_name, e)
        return False
