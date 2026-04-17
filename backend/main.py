import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import List, Optional
from datetime import datetime

from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from database import engine, get_db, Base
from models import ManagedApp, AppStatus, Incident, AlertLog
from schemas import AppCreate, AppUpdate, AppOut, IncidentOut, AlertLogOut, CommandResponse
import monitor

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# ─── WebSocket Manager ────────────────────────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        self.active.discard(ws) if hasattr(self.active, "discard") else None
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, data: dict):
        dead = []
        for ws in self.active:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

manager = ConnectionManager()


# ─── Lifespan ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    monitor.broadcast_fn = manager.broadcast
    task = asyncio.create_task(monitor.run_health_checks())
    logger.info("AppCTL started.")
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


# ─── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(title="AppCTL", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── WebSocket ────────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            await ws.receive_text()  # keep alive / ping
    except WebSocketDisconnect:
        manager.disconnect(ws)


# ─── App Registry CRUD ────────────────────────────────────────────────────────

@app.get("/api/apps", response_model=List[AppOut])
def list_apps(db: Session = Depends(get_db)):
    return db.query(ManagedApp).order_by(ManagedApp.name).all()


@app.post("/api/apps", response_model=AppOut, status_code=201)
def register_app(payload: AppCreate, db: Session = Depends(get_db)):
    existing = db.query(ManagedApp).filter(ManagedApp.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=409, detail="An app with this name already exists.")
    app_obj = ManagedApp(**payload.model_dump())
    db.add(app_obj)
    db.commit()
    db.refresh(app_obj)
    return app_obj


@app.get("/api/apps/{app_id}", response_model=AppOut)
def get_app(app_id: int, db: Session = Depends(get_db)):
    obj = db.query(ManagedApp).get(app_id)
    if not obj:
        raise HTTPException(status_code=404, detail="App not found.")
    return obj


@app.patch("/api/apps/{app_id}", response_model=AppOut)
def update_app(app_id: int, payload: AppUpdate, db: Session = Depends(get_db)):
    obj = db.query(ManagedApp).get(app_id)
    if not obj:
        raise HTTPException(status_code=404, detail="App not found.")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(obj, field, value)
    db.commit()
    db.refresh(obj)
    return obj


@app.delete("/api/apps/{app_id}", status_code=204)
def delete_app(app_id: int, db: Session = Depends(get_db)):
    obj = db.query(ManagedApp).get(app_id)
    if not obj:
        raise HTTPException(status_code=404, detail="App not found.")
    db.delete(obj)
    db.commit()


# ─── Start / Stop ─────────────────────────────────────────────────────────────

@app.post("/api/apps/{app_id}/start", response_model=CommandResponse)
async def start_app(app_id: int, db: Session = Depends(get_db)):
    obj = db.query(ManagedApp).get(app_id)
    if not obj:
        raise HTTPException(status_code=404, detail="App not found.")
    if not obj.start_command:
        raise HTTPException(status_code=400, detail="No start command configured.")

    obj.status = AppStatus.STARTING
    db.commit()
    await manager.broadcast({"event": "status_change", "app_id": obj.id, "app_name": obj.name, "status": "starting"})

    success, output = await asyncio.get_event_loop().run_in_executor(
        None, monitor.ssh_exec, obj, obj.start_command
    )

    db.refresh(obj)
    if not success:
        obj.status = AppStatus.OFFLINE
        db.commit()
    return CommandResponse(success=success, message="Start command executed." if success else "Start command failed.", output=output)


@app.post("/api/apps/{app_id}/stop", response_model=CommandResponse)
async def stop_app(app_id: int, db: Session = Depends(get_db)):
    obj = db.query(ManagedApp).get(app_id)
    if not obj:
        raise HTTPException(status_code=404, detail="App not found.")
    if not obj.stop_command:
        raise HTTPException(status_code=400, detail="No stop command configured.")

    obj.status = AppStatus.STOPPING
    db.commit()
    await manager.broadcast({"event": "status_change", "app_id": obj.id, "app_name": obj.name, "status": "stopping"})

    success, output = await asyncio.get_event_loop().run_in_executor(
        None, monitor.ssh_exec, obj, obj.stop_command
    )

    db.refresh(obj)
    if success:
        obj.status = AppStatus.OFFLINE
        db.commit()
    return CommandResponse(success=success, message="Stop command executed." if success else "Stop command failed.", output=output)


@app.post("/api/apps/{app_id}/check", response_model=AppOut)
async def force_check(app_id: int, db: Session = Depends(get_db)):
    """Force an immediate health check for a single app."""
    obj = db.query(ManagedApp).get(app_id)
    if not obj:
        raise HTTPException(status_code=404, detail="App not found.")
    is_up = await monitor.check_app_health(obj)
    obj.last_checked = datetime.utcnow()
    obj.status = AppStatus.ONLINE if is_up else AppStatus.OFFLINE
    if is_up:
        obj.last_seen_online = datetime.utcnow()
        obj.down_since = None
    elif obj.down_since is None:
        obj.down_since = datetime.utcnow()
    db.commit()
    db.refresh(obj)
    return obj


# ─── Incidents & Alerts ───────────────────────────────────────────────────────

@app.get("/api/apps/{app_id}/incidents", response_model=List[IncidentOut])
def get_incidents(app_id: int, limit: int = 50, db: Session = Depends(get_db)):
    return db.query(Incident).filter(Incident.app_id == app_id).order_by(Incident.started_at.desc()).limit(limit).all()


@app.get("/api/apps/{app_id}/alerts", response_model=List[AlertLogOut])
def get_alerts(app_id: int, limit: int = 50, db: Session = Depends(get_db)):
    return db.query(AlertLog).filter(AlertLog.app_id == app_id).order_by(AlertLog.sent_at.desc()).limit(limit).all()


@app.get("/api/incidents", response_model=List[IncidentOut])
def all_incidents(limit: int = 100, db: Session = Depends(get_db)):
    return db.query(Incident).order_by(Incident.started_at.desc()).limit(limit).all()


# ─── Stats ────────────────────────────────────────────────────────────────────

@app.get("/api/stats")
def get_stats(db: Session = Depends(get_db)):
    total = db.query(ManagedApp).count()
    online = db.query(ManagedApp).filter(ManagedApp.status == AppStatus.ONLINE).count()
    offline = db.query(ManagedApp).filter(ManagedApp.status == AppStatus.OFFLINE).count()
    unknown = db.query(ManagedApp).filter(ManagedApp.status == AppStatus.UNKNOWN).count()
    open_incidents = db.query(Incident).filter(Incident.resolved_at == None).count()
    return {
        "total": total,
        "online": online,
        "offline": offline,
        "unknown": unknown,
        "open_incidents": open_incidents,
    }


# ─── Serve Frontend ───────────────────────────────────────────────────────────

app.mount("/static", StaticFiles(directory="../frontend"), name="static")

@app.get("/", include_in_schema=False)
def serve_ui():
    return FileResponse("../frontend/index.html")
