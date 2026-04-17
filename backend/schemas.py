from pydantic import BaseModel, HttpUrl
from typing import Optional, List
from datetime import datetime
from models import AppStatus


class AppCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    url: str
    health_path: Optional[str] = "/"
    ssh_host: Optional[str] = ""
    ssh_port: Optional[int] = 22
    ssh_user: Optional[str] = ""
    ssh_key_path: Optional[str] = ""
    start_command: Optional[str] = ""
    stop_command: Optional[str] = ""
    tags: Optional[str] = ""


class AppUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None
    health_path: Optional[str] = None
    ssh_host: Optional[str] = None
    ssh_port: Optional[int] = None
    ssh_user: Optional[str] = None
    ssh_key_path: Optional[str] = None
    start_command: Optional[str] = None
    stop_command: Optional[str] = None
    tags: Optional[str] = None
    enabled: Optional[bool] = None


class AppOut(BaseModel):
    id: int
    name: str
    description: str
    url: str
    health_path: str
    ssh_host: str
    ssh_port: int
    ssh_user: str
    start_command: str
    stop_command: str
    status: AppStatus
    last_checked: Optional[datetime]
    last_seen_online: Optional[datetime]
    down_since: Optional[datetime]
    enabled: bool
    tags: str
    created_at: datetime

    class Config:
        from_attributes = True


class IncidentOut(BaseModel):
    id: int
    app_id: int
    started_at: datetime
    resolved_at: Optional[datetime]
    duration_seconds: Optional[int]
    notes: str

    class Config:
        from_attributes = True


class AlertLogOut(BaseModel):
    id: int
    app_id: int
    sent_at: datetime
    alert_type: str
    message: str
    success: bool

    class Config:
        from_attributes = True


class CommandResponse(BaseModel):
    success: bool
    message: str
    output: Optional[str] = ""
