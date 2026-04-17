from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Enum
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime
import enum


class AppStatus(str, enum.Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    UNKNOWN = "unknown"
    STARTING = "starting"
    STOPPING = "stopping"


class ManagedApp(Base):
    __tablename__ = "managed_apps"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), unique=True, nullable=False)
    description = Column(Text, default="")
    
    # Connectivity
    url = Column(String(512), nullable=False)       # e.g. http://192.168.1.10:8080
    health_path = Column(String(256), default="/")  # appended to url for health check
    
    # SSH for start/stop (optional)
    ssh_host = Column(String(256), default="")
    ssh_port = Column(Integer, default=22)
    ssh_user = Column(String(128), default="")
    ssh_key_path = Column(String(512), default="")  # path to private key on server
    start_command = Column(Text, default="")
    stop_command = Column(Text, default="")
    
    # Status tracking
    status = Column(Enum(AppStatus), default=AppStatus.UNKNOWN)
    last_checked = Column(DateTime, nullable=True)
    last_seen_online = Column(DateTime, nullable=True)
    down_since = Column(DateTime, nullable=True)
    alert_sent = Column(Boolean, default=False)     # alert sent for current outage?
    
    # Meta
    enabled = Column(Boolean, default=True)
    tags = Column(String(512), default="")          # comma-separated tags
    created_at = Column(DateTime, default=datetime.utcnow)

    incidents = relationship("Incident", back_populates="app", cascade="all, delete-orphan")
    alerts = relationship("AlertLog", back_populates="app", cascade="all, delete-orphan")


class Incident(Base):
    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True, index=True)
    app_id = Column(Integer, ForeignKey("managed_apps.id"), nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, nullable=True)  # filled on resolve
    notes = Column(Text, default="")

    app = relationship("ManagedApp", back_populates="incidents")


class AlertLog(Base):
    __tablename__ = "alert_logs"

    id = Column(Integer, primary_key=True, index=True)
    app_id = Column(Integer, ForeignKey("managed_apps.id"), nullable=False)
    sent_at = Column(DateTime, default=datetime.utcnow)
    alert_type = Column(String(64), default="email")
    message = Column(Text, default="")
    success = Column(Boolean, default=True)

    app = relationship("ManagedApp", back_populates="alerts")
