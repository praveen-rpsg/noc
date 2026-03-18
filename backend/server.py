from fastapi import FastAPI, APIRouter, HTTPException, Depends, status, WebSocket, WebSocketDisconnect
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict, EmailStr
from typing import List, Optional, Dict, Any, Set
import uuid
from datetime import datetime, timezone, timedelta
import jwt
import bcrypt
import asyncio
from enum import Enum
import json
import paramiko
import io
import telnetlib3
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from agents import (
    generate_activation_codes, Agent, AgentCreate, AgentUpdate,
    ActivationCode, EscalationContact, EscalationContactCreate, ESCALATION_LEVELS
)

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# JWT Config
JWT_SECRET = os.environ.get('JWT_SECRET', 'noc-commander-secret')
JWT_ALGORITHM = os.environ.get('JWT_ALGORITHM', 'HS256')
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get('ACCESS_TOKEN_EXPIRE_MINUTES', 1440))

# Emergent LLM Key
EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY', '')

# Office 365 SMTP Configuration
SMTP_SERVER = os.environ.get('SMTP_SERVER', 'smtp.office365.com')
SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
SMTP_USERNAME = os.environ.get('SMTP_USERNAME', '')
SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD', '')
EMAIL_FROM = os.environ.get('EMAIL_FROM', 'noc@atech.com')

# Create the main app
app = FastAPI(title="ATECH NOC Commander API", version="2.0.0")

# WebSocket connections for real-time alerts
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
    
    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass

ws_manager = ConnectionManager()

# Notification queue for alerts
notification_queue: List[dict] = []

# Create routers
api_router = APIRouter(prefix="/api")
auth_router = APIRouter(prefix="/auth", tags=["Authentication"])
devices_router = APIRouter(prefix="/devices", tags=["Devices"])
alerts_router = APIRouter(prefix="/alerts", tags=["Alerts"])
incidents_router = APIRouter(prefix="/incidents", tags=["Incidents"])
performance_router = APIRouter(prefix="/performance", tags=["Performance"])
assets_router = APIRouter(prefix="/assets", tags=["Assets"])
reports_router = APIRouter(prefix="/reports", tags=["Reports"])
config_router = APIRouter(prefix="/config", tags=["Configuration"])
sla_router = APIRouter(prefix="/sla", tags=["SLA"])
ai_router = APIRouter(prefix="/ai", tags=["AI"])
dashboard_router = APIRouter(prefix="/dashboard", tags=["Dashboard"])
topology_router = APIRouter(prefix="/topology", tags=["Topology"])
ssh_router = APIRouter(prefix="/ssh", tags=["SSH"])
notifications_router = APIRouter(prefix="/notifications", tags=["Notifications"])
agents_router = APIRouter(prefix="/agents", tags=["Agents"])
snmp_router = APIRouter(prefix="/snmp", tags=["SNMP"])
telnet_router = APIRouter(prefix="/telnet", tags=["Telnet"])
escalation_router = APIRouter(prefix="/escalation", tags=["Escalation"])

security = HTTPBearer()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ===================== ENUMS =====================
class DeviceType(str, Enum):
    ROUTER = "router"
    SWITCH = "switch"
    FIREWALL = "firewall"
    LOAD_BALANCER = "load_balancer"
    SERVER = "server"
    VM = "virtual_machine"
    CLOUD_INSTANCE = "cloud_instance"
    ACCESS_POINT = "access_point"

class DeviceStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    DEGRADED = "degraded"
    MAINTENANCE = "maintenance"
    UNKNOWN = "unknown"

class AlertSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"

class AlertStatus(str, Enum):
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"

class IncidentPriority(str, Enum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"

class IncidentStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    ESCALATED = "escalated"
    RESOLVED = "resolved"
    CLOSED = "closed"

# ===================== MODELS =====================
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str
    role: str = "operator"

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class User(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: EmailStr
    name: str
    role: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: User

class Device(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    type: DeviceType
    ip_address: str
    location: str
    status: DeviceStatus = DeviceStatus.ONLINE
    vendor: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    firmware_version: Optional[str] = None
    config_url: Optional[str] = None  # URL to device configuration page
    last_seen: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    uptime_hours: int = 0
    tags: List[str] = []
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class DeviceCreate(BaseModel):
    name: str
    type: DeviceType
    ip_address: str
    location: str
    vendor: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    firmware_version: Optional[str] = None
    config_url: Optional[str] = None  # URL to device configuration page
    tags: List[str] = []

class Alert(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    device_id: str
    device_name: str
    severity: AlertSeverity
    status: AlertStatus = AlertStatus.ACTIVE
    title: str
    description: str
    metric_name: Optional[str] = None
    metric_value: Optional[float] = None
    threshold: Optional[float] = None
    acknowledged_by: Optional[str] = None
    resolved_by: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None

class AlertCreate(BaseModel):
    device_id: str
    device_name: str
    severity: AlertSeverity
    title: str
    description: str
    metric_name: Optional[str] = None
    metric_value: Optional[float] = None
    threshold: Optional[float] = None

class Incident(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    ticket_number: str = Field(default_factory=lambda: f"INC-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:6].upper()}")
    title: str
    description: str
    priority: IncidentPriority
    status: IncidentStatus = IncidentStatus.OPEN
    category: str
    affected_devices: List[str] = []
    related_alerts: List[str] = []
    assigned_to: Optional[str] = None
    escalation_level: int = 1
    ai_suggestions: Optional[str] = None
    root_cause: Optional[str] = None
    resolution: Optional[str] = None
    created_by: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: Optional[datetime] = None
    sla_breach: bool = False

class IncidentCreate(BaseModel):
    title: str
    description: str
    priority: IncidentPriority
    category: str
    affected_devices: List[str] = []
    related_alerts: List[str] = []

class PerformanceMetric(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    device_id: str
    device_name: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    bandwidth_in: float
    bandwidth_out: float
    latency_ms: float
    packet_loss: float
    uptime_hours: int

class Asset(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    asset_tag: str
    type: str
    vendor: str
    model: str
    serial_number: str
    location: str
    owner: str
    status: str = "active"
    purchase_date: Optional[str] = None
    warranty_expiry: Optional[str] = None
    eol_date: Optional[str] = None
    contract_details: Optional[str] = None
    license_info: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class AssetCreate(BaseModel):
    name: str
    asset_tag: str
    type: str
    vendor: str
    model: str
    serial_number: str
    location: str
    owner: str
    purchase_date: Optional[str] = None
    warranty_expiry: Optional[str] = None
    eol_date: Optional[str] = None
    contract_details: Optional[str] = None
    license_info: Optional[str] = None

class Report(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    type: str
    period_start: str
    period_end: str
    generated_by: str
    content: Dict[str, Any]
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Configuration(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    device_id: str
    device_name: str
    config_type: str
    config_data: str
    version: int = 1
    backup_date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str
    is_compliant: bool = True
    compliance_notes: Optional[str] = None

class SLARecord(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str
    priority: IncidentPriority
    response_time_target_mins: int
    resolution_time_target_mins: int
    actual_response_time_mins: Optional[int] = None
    actual_resolution_time_mins: Optional[int] = None
    response_sla_met: Optional[bool] = None
    resolution_sla_met: Optional[bool] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class AIAnalysisRequest(BaseModel):
    context: str
    query: str
    incident_id: Optional[str] = None

# ===================== HELPER FUNCTIONS =====================
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

def create_token(user_id: str, email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": user_id, "email": email, "exp": expire}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0, "password_hash": 0})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

def serialize_doc(doc: dict) -> dict:
    """Remove MongoDB _id and serialize datetime fields"""
    if doc and "_id" in doc:
        del doc["_id"]
    for key, value in doc.items():
        if isinstance(value, datetime):
            doc[key] = value.isoformat()
    return doc

# ===================== AI SERVICE =====================
async def get_ai_analysis(context: str, query: str) -> str:
    """Get AI analysis using Emergent LLM"""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"noc-{str(uuid.uuid4())[:8]}",
            system_message="""You are an expert Network Operation Center (NOC) AI assistant. 
You help NOC engineers with:
- Troubleshooting network and infrastructure issues
- Root Cause Analysis (RCA)
- Providing step-by-step resolution suggestions
- Analyzing performance metrics and logs
- Identifying patterns and anomalies
- Recommending preventive measures

Be concise, technical, and actionable in your responses."""
        ).with_model("openai", "gpt-5.2")
        
        user_message = UserMessage(text=f"Context: {context}\n\nQuery: {query}")
        response = await chat.send_message(user_message)
        return response
    except Exception as e:
        logger.error(f"AI analysis error: {e}")
        return f"AI analysis temporarily unavailable. Error: {str(e)}"

# ===================== AUTH ROUTES =====================
@auth_router.post("/register", response_model=TokenResponse)
async def register(user_data: UserCreate):
    existing = await db.users.find_one({"email": user_data.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    user = User(email=user_data.email, name=user_data.name, role=user_data.role)
    user_dict = user.model_dump()
    user_dict["password_hash"] = hash_password(user_data.password)
    user_dict["created_at"] = user_dict["created_at"].isoformat()
    
    await db.users.insert_one(user_dict)
    token = create_token(user.id, user.email)
    return TokenResponse(access_token=token, user=user)

@auth_router.post("/login", response_model=TokenResponse)
async def login(credentials: UserLogin):
    user_doc = await db.users.find_one({"email": credentials.email})
    if not user_doc or not verify_password(credentials.password, user_doc.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    user = User(
        id=user_doc["id"],
        email=user_doc["email"],
        name=user_doc["name"],
        role=user_doc["role"],
        created_at=datetime.fromisoformat(user_doc["created_at"]) if isinstance(user_doc["created_at"], str) else user_doc["created_at"]
    )
    token = create_token(user.id, user.email)
    return TokenResponse(access_token=token, user=user)

@auth_router.get("/me", response_model=User)
async def get_me(current_user: dict = Depends(get_current_user)):
    return User(**current_user)

# ===================== DEVICE ROUTES =====================
@devices_router.get("", response_model=List[Device])
async def get_devices(current_user: dict = Depends(get_current_user)):
    devices = await db.devices.find({}, {"_id": 0}).to_list(1000)
    return [Device(**serialize_doc(d)) for d in devices]

@devices_router.get("/{device_id}", response_model=Device)
async def get_device(device_id: str, current_user: dict = Depends(get_current_user)):
    device = await db.devices.find_one({"id": device_id}, {"_id": 0})
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return Device(**serialize_doc(device))

@devices_router.post("", response_model=Device)
async def create_device(device_data: DeviceCreate, current_user: dict = Depends(get_current_user)):
    device = Device(**device_data.model_dump())
    device_dict = device.model_dump()
    device_dict["created_at"] = device_dict["created_at"].isoformat()
    device_dict["last_seen"] = device_dict["last_seen"].isoformat()
    await db.devices.insert_one(device_dict)
    return device

@devices_router.put("/{device_id}", response_model=Device)
async def update_device(device_id: str, device_data: DeviceCreate, current_user: dict = Depends(get_current_user)):
    existing = await db.devices.find_one({"id": device_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Device not found")
    
    update_data = device_data.model_dump()
    update_data["last_seen"] = datetime.now(timezone.utc).isoformat()
    await db.devices.update_one({"id": device_id}, {"$set": update_data})
    
    updated = await db.devices.find_one({"id": device_id}, {"_id": 0})
    return Device(**serialize_doc(updated))

@devices_router.put("/{device_id}/config-url")
async def update_device_config_url(device_id: str, config_url: str = None, current_user: dict = Depends(get_current_user)):
    """Update device configuration URL"""
    existing = await db.devices.find_one({"id": device_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Device not found")
    
    await db.devices.update_one({"id": device_id}, {"$set": {"config_url": config_url}})
    return {"message": "Config URL updated", "config_url": config_url}

@devices_router.delete("/{device_id}")
async def delete_device(device_id: str, current_user: dict = Depends(get_current_user)):
    result = await db.devices.delete_one({"id": device_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Device not found")
    return {"message": "Device deleted"}

# ===================== ALERT ROUTES =====================
@alerts_router.get("", response_model=List[Alert])
async def get_alerts(status: Optional[str] = None, severity: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    query = {}
    if status:
        query["status"] = status
    if severity:
        query["severity"] = severity
    alerts = await db.alerts.find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return [Alert(**serialize_doc(a)) for a in alerts]

@alerts_router.post("", response_model=Alert)
async def create_alert(alert_data: AlertCreate, current_user: dict = Depends(get_current_user)):
    alert = Alert(**alert_data.model_dump())
    alert_dict = alert.model_dump()
    alert_dict["created_at"] = alert_dict["created_at"].isoformat()
    await db.alerts.insert_one(alert_dict)
    
    # Send WebSocket notification for critical alerts
    if alert.severity in [AlertSeverity.CRITICAL, AlertSeverity.HIGH]:
        await ws_manager.broadcast({
            "type": "alert",
            "data": {
                "id": alert.id,
                "title": alert.title,
                "severity": alert.severity.value,
                "device_name": alert.device_name,
                "created_at": alert_dict["created_at"]
            }
        })
    
    return alert

@alerts_router.put("/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str, current_user: dict = Depends(get_current_user)):
    result = await db.alerts.update_one(
        {"id": alert_id},
        {"$set": {
            "status": AlertStatus.ACKNOWLEDGED.value,
            "acknowledged_by": current_user["name"],
            "acknowledged_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"message": "Alert acknowledged"}

@alerts_router.put("/{alert_id}/resolve")
async def resolve_alert(alert_id: str, current_user: dict = Depends(get_current_user)):
    result = await db.alerts.update_one(
        {"id": alert_id},
        {"$set": {
            "status": AlertStatus.RESOLVED.value,
            "resolved_by": current_user["name"],
            "resolved_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"message": "Alert resolved"}

# ===================== INCIDENT ROUTES =====================
@incidents_router.get("", response_model=List[Incident])
async def get_incidents(status: Optional[str] = None, priority: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    query = {}
    if status:
        query["status"] = status
    if priority:
        query["priority"] = priority
    incidents = await db.incidents.find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return [Incident(**serialize_doc(i)) for i in incidents]

@incidents_router.get("/{incident_id}", response_model=Incident)
async def get_incident(incident_id: str, current_user: dict = Depends(get_current_user)):
    incident = await db.incidents.find_one({"id": incident_id}, {"_id": 0})
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return Incident(**serialize_doc(incident))

@incidents_router.post("", response_model=Incident)
async def create_incident(incident_data: IncidentCreate, current_user: dict = Depends(get_current_user)):
    incident = Incident(**incident_data.model_dump(), created_by=current_user["name"])
    incident_dict = incident.model_dump()
    incident_dict["created_at"] = incident_dict["created_at"].isoformat()
    incident_dict["updated_at"] = incident_dict["updated_at"].isoformat()
    await db.incidents.insert_one(incident_dict)
    
    # Create SLA record
    sla_targets = {"P1": (15, 60), "P2": (30, 240), "P3": (60, 480), "P4": (120, 1440)}
    target = sla_targets.get(incident.priority.value, (60, 480))
    sla_record = SLARecord(
        incident_id=incident.id,
        priority=incident.priority,
        response_time_target_mins=target[0],
        resolution_time_target_mins=target[1]
    )
    sla_dict = sla_record.model_dump()
    sla_dict["created_at"] = sla_dict["created_at"].isoformat()
    await db.sla_records.insert_one(sla_dict)
    
    return incident

@incidents_router.put("/{incident_id}", response_model=Incident)
async def update_incident(incident_id: str, update_data: dict, current_user: dict = Depends(get_current_user)):
    existing = await db.incidents.find_one({"id": incident_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Incident not found")
    
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    if update_data.get("status") in ["resolved", "closed"]:
        update_data["resolved_at"] = datetime.now(timezone.utc).isoformat()
    
    await db.incidents.update_one({"id": incident_id}, {"$set": update_data})
    updated = await db.incidents.find_one({"id": incident_id}, {"_id": 0})
    return Incident(**serialize_doc(updated))

@incidents_router.post("/{incident_id}/ai-analysis")
async def get_incident_ai_analysis(incident_id: str, current_user: dict = Depends(get_current_user)):
    incident = await db.incidents.find_one({"id": incident_id}, {"_id": 0})
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    
    context = f"""
Incident: {incident['title']}
Description: {incident['description']}
Priority: {incident['priority']}
Category: {incident['category']}
Status: {incident['status']}
Affected Devices: {', '.join(incident.get('affected_devices', []))}
"""
    
    analysis = await get_ai_analysis(
        context,
        "Provide troubleshooting steps, probable root cause, and resolution recommendations for this incident."
    )
    
    await db.incidents.update_one(
        {"id": incident_id},
        {"$set": {"ai_suggestions": analysis, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    return {"analysis": analysis}

# ===================== PERFORMANCE ROUTES =====================
@performance_router.get("", response_model=List[PerformanceMetric])
async def get_performance_metrics(device_id: Optional[str] = None, hours: int = 24, current_user: dict = Depends(get_current_user)):
    query = {}
    if device_id:
        query["device_id"] = device_id
    
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    query["timestamp"] = {"$gte": cutoff.isoformat()}
    
    metrics = await db.performance_metrics.find(query, {"_id": 0}).sort("timestamp", -1).to_list(5000)
    return [PerformanceMetric(**serialize_doc(m)) for m in metrics]

@performance_router.post("", response_model=PerformanceMetric)
async def create_performance_metric(metric_data: dict, current_user: dict = Depends(get_current_user)):
    metric = PerformanceMetric(**metric_data)
    metric_dict = metric.model_dump()
    metric_dict["timestamp"] = metric_dict["timestamp"].isoformat()
    await db.performance_metrics.insert_one(metric_dict)
    return metric

# ===================== ASSET ROUTES =====================
@assets_router.get("", response_model=List[Asset])
async def get_assets(current_user: dict = Depends(get_current_user)):
    assets = await db.assets.find({}, {"_id": 0}).to_list(1000)
    return [Asset(**serialize_doc(a)) for a in assets]

@assets_router.get("/{asset_id}", response_model=Asset)
async def get_asset(asset_id: str, current_user: dict = Depends(get_current_user)):
    asset = await db.assets.find_one({"id": asset_id}, {"_id": 0})
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return Asset(**serialize_doc(asset))

@assets_router.post("", response_model=Asset)
async def create_asset(asset_data: AssetCreate, current_user: dict = Depends(get_current_user)):
    asset = Asset(**asset_data.model_dump())
    asset_dict = asset.model_dump()
    asset_dict["created_at"] = asset_dict["created_at"].isoformat()
    await db.assets.insert_one(asset_dict)
    return asset

@assets_router.put("/{asset_id}", response_model=Asset)
async def update_asset(asset_id: str, asset_data: AssetCreate, current_user: dict = Depends(get_current_user)):
    existing = await db.assets.find_one({"id": asset_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Asset not found")
    
    await db.assets.update_one({"id": asset_id}, {"$set": asset_data.model_dump()})
    updated = await db.assets.find_one({"id": asset_id}, {"_id": 0})
    return Asset(**serialize_doc(updated))

@assets_router.delete("/{asset_id}")
async def delete_asset(asset_id: str, current_user: dict = Depends(get_current_user)):
    result = await db.assets.delete_one({"id": asset_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Asset not found")
    return {"message": "Asset deleted"}

# ===================== REPORT ROUTES =====================
@reports_router.get("", response_model=List[Report])
async def get_reports(report_type: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    query = {}
    if report_type:
        query["type"] = report_type
    reports = await db.reports.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
    return [Report(**serialize_doc(r)) for r in reports]

@reports_router.post("/generate")
async def generate_report(report_type: str, period_start: str, period_end: str, current_user: dict = Depends(get_current_user)):
    # Generate report based on type
    content = {}
    
    if report_type == "daily_health":
        devices = await db.devices.find({}, {"_id": 0}).to_list(1000)
        alerts = await db.alerts.find({"status": "active"}, {"_id": 0}).to_list(1000)
        content = {
            "total_devices": len(devices),
            "online_devices": len([d for d in devices if d.get("status") == "online"]),
            "active_alerts": len(alerts),
            "critical_alerts": len([a for a in alerts if a.get("severity") == "critical"])
        }
    elif report_type == "incident_summary":
        incidents = await db.incidents.find({}, {"_id": 0}).to_list(1000)
        content = {
            "total_incidents": len(incidents),
            "open_incidents": len([i for i in incidents if i.get("status") == "open"]),
            "resolved_incidents": len([i for i in incidents if i.get("status") in ["resolved", "closed"]]),
            "by_priority": {
                "P1": len([i for i in incidents if i.get("priority") == "P1"]),
                "P2": len([i for i in incidents if i.get("priority") == "P2"]),
                "P3": len([i for i in incidents if i.get("priority") == "P3"]),
                "P4": len([i for i in incidents if i.get("priority") == "P4"])
            }
        }
    elif report_type == "sla_compliance":
        sla_records = await db.sla_records.find({}, {"_id": 0}).to_list(1000)
        met_count = len([s for s in sla_records if s.get("resolution_sla_met") == True])
        total = len(sla_records) or 1
        content = {
            "total_tracked": len(sla_records),
            "sla_met": met_count,
            "sla_breached": len(sla_records) - met_count,
            "compliance_percentage": round(met_count / total * 100, 2)
        }
    
    report = Report(
        title=f"{report_type.replace('_', ' ').title()} Report",
        type=report_type,
        period_start=period_start,
        period_end=period_end,
        generated_by=current_user["name"],
        content=content
    )
    
    report_dict = report.model_dump()
    report_dict["created_at"] = report_dict["created_at"].isoformat()
    await db.reports.insert_one(report_dict)
    
    return report

# ===================== CONFIG ROUTES =====================
@config_router.get("", response_model=List[Configuration])
async def get_configurations(device_id: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    query = {}
    if device_id:
        query["device_id"] = device_id
    configs = await db.configurations.find(query, {"_id": 0}).sort("backup_date", -1).to_list(1000)
    return [Configuration(**serialize_doc(c)) for c in configs]

@config_router.post("/backup")
async def create_config_backup(device_id: str, config_type: str, config_data: str, current_user: dict = Depends(get_current_user)):
    device = await db.devices.find_one({"id": device_id}, {"_id": 0})
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    # Get latest version
    latest = await db.configurations.find_one(
        {"device_id": device_id, "config_type": config_type},
        sort=[("version", -1)]
    )
    version = (latest.get("version", 0) if latest else 0) + 1
    
    config = Configuration(
        device_id=device_id,
        device_name=device["name"],
        config_type=config_type,
        config_data=config_data,
        version=version,
        created_by=current_user["name"]
    )
    
    config_dict = config.model_dump()
    config_dict["backup_date"] = config_dict["backup_date"].isoformat()
    await db.configurations.insert_one(config_dict)
    
    return {"message": "Configuration backed up", "version": version}

# ===================== SLA ROUTES =====================
@sla_router.get("", response_model=List[SLARecord])
async def get_sla_records(current_user: dict = Depends(get_current_user)):
    records = await db.sla_records.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return [SLARecord(**serialize_doc(r)) for r in records]

@sla_router.get("/metrics")
async def get_sla_metrics(current_user: dict = Depends(get_current_user)):
    records = await db.sla_records.find({}, {"_id": 0}).to_list(1000)
    
    total = len(records) or 1
    response_met = len([r for r in records if r.get("response_sla_met") == True])
    resolution_met = len([r for r in records if r.get("resolution_sla_met") == True])
    
    return {
        "total_tracked": len(records),
        "response_sla_compliance": round(response_met / total * 100, 2),
        "resolution_sla_compliance": round(resolution_met / total * 100, 2),
        "overall_compliance": round((response_met + resolution_met) / (total * 2) * 100, 2)
    }

# ===================== AI ROUTES =====================
@ai_router.post("/analyze")
async def analyze_with_ai(request: AIAnalysisRequest, current_user: dict = Depends(get_current_user)):
    analysis = await get_ai_analysis(request.context, request.query)
    return {"analysis": analysis}

class TracerouteRequest(BaseModel):
    target: str
    traceroute_output: str

class LogAnalysisRequest(BaseModel):
    logs: str

@ai_router.post("/traceroute-analysis")
async def analyze_traceroute(request: TracerouteRequest, current_user: dict = Depends(get_current_user)):
    context = f"Traceroute to {request.target}:\n{request.traceroute_output}"
    analysis = await get_ai_analysis(
        context,
        "Analyze this traceroute output. Identify where the connection might be dropping or experiencing high latency. Provide recommendations."
    )
    return {"analysis": analysis}

@ai_router.post("/log-analysis")
async def analyze_logs(request: LogAnalysisRequest, current_user: dict = Depends(get_current_user)):
    analysis = await get_ai_analysis(
        request.logs,
        "Analyze these logs for errors, warnings, and anomalies. Identify patterns and provide recommendations."
    )
    return {"analysis": analysis}

# ===================== DASHBOARD ROUTES =====================
@dashboard_router.get("/stats")
async def get_dashboard_stats(current_user: dict = Depends(get_current_user)):
    devices = await db.devices.find({}, {"_id": 0}).to_list(1000)
    alerts = await db.alerts.find({}, {"_id": 0}).to_list(1000)
    incidents = await db.incidents.find({}, {"_id": 0}).to_list(1000)
    
    active_alerts = [a for a in alerts if a.get("status") == "active"]
    open_incidents = [i for i in incidents if i.get("status") in ["open", "in_progress"]]
    
    # Calculate KPIs
    resolved_incidents = [i for i in incidents if i.get("resolved_at")]
    mttd = 0
    mttr = 0
    
    if resolved_incidents:
        # Simplified MTTR calculation
        mttr = 45  # Demo value in minutes
    
    online_devices = len([d for d in devices if d.get("status") == "online"])
    total_devices = len(devices) or 1
    uptime_pct = round(online_devices / total_devices * 100, 2)
    
    return {
        "devices": {
            "total": len(devices),
            "online": online_devices,
            "offline": len([d for d in devices if d.get("status") == "offline"]),
            "degraded": len([d for d in devices if d.get("status") == "degraded"]),
            "maintenance": len([d for d in devices if d.get("status") == "maintenance"])
        },
        "alerts": {
            "total": len(alerts),
            "active": len(active_alerts),
            "critical": len([a for a in active_alerts if a.get("severity") == "critical"]),
            "high": len([a for a in active_alerts if a.get("severity") == "high"]),
            "medium": len([a for a in active_alerts if a.get("severity") == "medium"]),
            "low": len([a for a in active_alerts if a.get("severity") == "low"])
        },
        "incidents": {
            "total": len(incidents),
            "open": len(open_incidents),
            "p1_open": len([i for i in open_incidents if i.get("priority") == "P1"]),
            "p2_open": len([i for i in open_incidents if i.get("priority") == "P2"])
        },
        "kpis": {
            "uptime_percentage": uptime_pct,
            "mttd_minutes": 5,
            "mttr_minutes": mttr,
            "sla_compliance": 98.5,
            "fcr_rate": 75.0
        }
    }

@dashboard_router.get("/recent-alerts")
async def get_recent_alerts(limit: int = 10, current_user: dict = Depends(get_current_user)):
    alerts = await db.alerts.find({}, {"_id": 0}).sort("created_at", -1).to_list(limit)
    return [serialize_doc(a) for a in alerts]

@dashboard_router.get("/recent-incidents")
async def get_recent_incidents(limit: int = 10, current_user: dict = Depends(get_current_user)):
    incidents = await db.incidents.find({}, {"_id": 0}).sort("created_at", -1).to_list(limit)
    return [serialize_doc(i) for i in incidents]

# ===================== SEED DATA =====================
@api_router.post("/seed")
async def seed_demo_data(current_user: dict = Depends(get_current_user)):
    """Seed database with demo data"""
    import random
    
    # Clear existing data
    await db.devices.delete_many({})
    await db.alerts.delete_many({})
    await db.incidents.delete_many({})
    await db.performance_metrics.delete_many({})
    await db.assets.delete_many({})
    
    # Create demo devices
    demo_devices = [
        {"name": "Core-Router-01", "type": "router", "ip_address": "10.0.1.1", "location": "DC-East", "vendor": "Cisco", "model": "ASR 9000", "status": "online"},
        {"name": "Core-Switch-01", "type": "switch", "ip_address": "10.0.1.2", "location": "DC-East", "vendor": "Cisco", "model": "Catalyst 9500", "status": "online"},
        {"name": "Firewall-01", "type": "firewall", "ip_address": "10.0.1.3", "location": "DC-East", "vendor": "Palo Alto", "model": "PA-5260", "status": "online"},
        {"name": "Load-Balancer-01", "type": "load_balancer", "ip_address": "10.0.1.4", "location": "DC-East", "vendor": "F5", "model": "BIG-IP i5800", "status": "online"},
        {"name": "Server-Web-01", "type": "server", "ip_address": "10.0.2.10", "location": "DC-East", "vendor": "Dell", "model": "PowerEdge R750", "status": "online"},
        {"name": "Server-Web-02", "type": "server", "ip_address": "10.0.2.11", "location": "DC-East", "vendor": "Dell", "model": "PowerEdge R750", "status": "degraded"},
        {"name": "Server-DB-01", "type": "server", "ip_address": "10.0.3.10", "location": "DC-East", "vendor": "HP", "model": "ProLiant DL380", "status": "online"},
        {"name": "AWS-Instance-01", "type": "cloud_instance", "ip_address": "172.31.1.10", "location": "AWS-us-east-1", "vendor": "AWS", "model": "c5.xlarge", "status": "online"},
        {"name": "Azure-VM-01", "type": "cloud_instance", "ip_address": "172.16.1.10", "location": "Azure-EastUS", "vendor": "Azure", "model": "Standard_D4s_v3", "status": "online"},
        {"name": "Edge-Router-NYC", "type": "router", "ip_address": "10.1.1.1", "location": "NYC-Office", "vendor": "Juniper", "model": "MX240", "status": "online"},
        {"name": "Edge-Switch-NYC", "type": "switch", "ip_address": "10.1.1.2", "location": "NYC-Office", "vendor": "Arista", "model": "7050X3", "status": "offline"},
        {"name": "WiFi-AP-Floor1", "type": "access_point", "ip_address": "10.1.2.10", "location": "NYC-Office", "vendor": "Aruba", "model": "AP-535", "status": "online"},
    ]
    
    for d in demo_devices:
        device = Device(
            **d,
            cpu_usage=random.uniform(20, 80),
            memory_usage=random.uniform(30, 70),
            uptime_hours=random.randint(100, 5000)
        )
        device_dict = device.model_dump()
        device_dict["created_at"] = device_dict["created_at"].isoformat()
        device_dict["last_seen"] = device_dict["last_seen"].isoformat()
        await db.devices.insert_one(device_dict)
    
    # Get device list for alerts
    devices = await db.devices.find({}, {"_id": 0}).to_list(20)
    
    # Create demo alerts
    alert_templates = [
        {"severity": "critical", "title": "High CPU Usage", "description": "CPU usage exceeded 90% threshold", "metric_name": "cpu_usage", "threshold": 90},
        {"severity": "high", "title": "Memory Usage Warning", "description": "Memory usage at 85%", "metric_name": "memory_usage", "threshold": 85},
        {"severity": "medium", "title": "Disk Space Low", "description": "Disk usage at 80%", "metric_name": "disk_usage", "threshold": 80},
        {"severity": "critical", "title": "Device Unreachable", "description": "Device not responding to ping", "metric_name": "availability", "threshold": 0},
        {"severity": "high", "title": "High Latency Detected", "description": "Network latency exceeded 100ms", "metric_name": "latency", "threshold": 100},
        {"severity": "low", "title": "Interface Flapping", "description": "Network interface experiencing intermittent connectivity", "metric_name": "interface_status", "threshold": 0},
    ]
    
    for i, template in enumerate(alert_templates[:4]):
        device = devices[i % len(devices)]
        alert = Alert(
            device_id=device["id"],
            device_name=device["name"],
            severity=AlertSeverity(template["severity"]),
            title=template["title"],
            description=template["description"],
            metric_name=template["metric_name"],
            metric_value=random.uniform(template["threshold"], template["threshold"] + 15),
            threshold=template["threshold"]
        )
        alert_dict = alert.model_dump()
        alert_dict["created_at"] = alert_dict["created_at"].isoformat()
        await db.alerts.insert_one(alert_dict)
    
    # Create demo incidents
    incident_templates = [
        {"title": "Network Outage - NYC Office", "description": "Complete network outage affecting NYC office. All users unable to connect.", "priority": "P1", "category": "Network"},
        {"title": "Web Server Performance Degradation", "description": "Server-Web-02 showing high response times and increased error rates.", "priority": "P2", "category": "Server"},
        {"title": "Firewall Policy Update Required", "description": "New application requires firewall rule changes.", "priority": "P3", "category": "Security"},
        {"title": "Backup Job Failure", "description": "Nightly backup job for DB server failed.", "priority": "P2", "category": "Backup"},
    ]
    
    for template in incident_templates:
        incident = Incident(
            title=template["title"],
            description=template["description"],
            priority=IncidentPriority(template["priority"]),
            category=template["category"],
            created_by=current_user["name"],
            affected_devices=[devices[0]["id"]]
        )
        incident_dict = incident.model_dump()
        incident_dict["created_at"] = incident_dict["created_at"].isoformat()
        incident_dict["updated_at"] = incident_dict["updated_at"].isoformat()
        await db.incidents.insert_one(incident_dict)
    
    # Create demo assets
    demo_assets = [
        {"name": "Core Router", "asset_tag": "NET-001", "type": "Network", "vendor": "Cisco", "model": "ASR 9000", "serial_number": "SN123456", "location": "DC-East", "owner": "Network Team", "warranty_expiry": "2025-12-31"},
        {"name": "Primary Database Server", "asset_tag": "SRV-001", "type": "Server", "vendor": "Dell", "model": "PowerEdge R750", "serial_number": "SN789012", "location": "DC-East", "owner": "Infrastructure Team", "warranty_expiry": "2026-06-30"},
        {"name": "Firewall Primary", "asset_tag": "SEC-001", "type": "Security", "vendor": "Palo Alto", "model": "PA-5260", "serial_number": "SN345678", "location": "DC-East", "owner": "Security Team", "eol_date": "2027-01-01"},
    ]
    
    for a in demo_assets:
        asset = Asset(**a)
        asset_dict = asset.model_dump()
        asset_dict["created_at"] = asset_dict["created_at"].isoformat()
        await db.assets.insert_one(asset_dict)
    
    # Create demo performance metrics
    for device in devices[:5]:
        for i in range(24):
            metric = PerformanceMetric(
                device_id=device["id"],
                device_name=device["name"],
                timestamp=datetime.now(timezone.utc) - timedelta(hours=i),
                cpu_usage=random.uniform(20, 80),
                memory_usage=random.uniform(30, 70),
                disk_usage=random.uniform(40, 75),
                bandwidth_in=random.uniform(100, 900),
                bandwidth_out=random.uniform(50, 500),
                latency_ms=random.uniform(1, 50),
                packet_loss=random.uniform(0, 2),
                uptime_hours=random.randint(100, 5000)
            )
            metric_dict = metric.model_dump()
            metric_dict["timestamp"] = metric_dict["timestamp"].isoformat()
            await db.performance_metrics.insert_one(metric_dict)
    
    return {"message": "Demo data seeded successfully"}

# ===================== WEBSOCKET ROUTES =====================
@app.websocket("/ws/alerts")
async def websocket_alerts(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep connection alive and listen for pings
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)

# ===================== TOPOLOGY ROUTES =====================
@topology_router.get("/data")
async def get_topology_data(current_user: dict = Depends(get_current_user)):
    """Get network topology data for visualization"""
    devices = await db.devices.find({}, {"_id": 0}).to_list(1000)
    
    nodes = []
    links = []
    
    # Group devices by location and type
    location_groups = {}
    for device in devices:
        loc = device.get("location", "Unknown")
        if loc not in location_groups:
            location_groups[loc] = {"core": [], "edge": [], "servers": [], "cloud": []}
        
        device_type = device.get("type", "")
        node = {
            "id": device["id"],
            "name": device["name"],
            "type": device_type,
            "status": device.get("status", "unknown"),
            "ip": device.get("ip_address", ""),
            "location": loc,
            "group": loc
        }
        nodes.append(node)
        
        if device_type in ["router", "switch", "firewall", "load_balancer"]:
            location_groups[loc]["core"].append(device["id"])
        elif device_type in ["server", "virtual_machine"]:
            location_groups[loc]["servers"].append(device["id"])
        elif device_type == "cloud_instance":
            location_groups[loc]["cloud"].append(device["id"])
        else:
            location_groups[loc]["edge"].append(device["id"])
    
    # Create links based on network hierarchy
    for loc, groups in location_groups.items():
        # Connect core devices to each other
        core_devices = groups["core"]
        for i, device_id in enumerate(core_devices):
            if i > 0:
                links.append({"source": core_devices[0], "target": device_id, "type": "core"})
        
        # Connect servers to first core device
        if core_devices:
            for server_id in groups["servers"]:
                links.append({"source": core_devices[0], "target": server_id, "type": "server"})
            for cloud_id in groups["cloud"]:
                links.append({"source": core_devices[0], "target": cloud_id, "type": "cloud"})
            for edge_id in groups["edge"]:
                links.append({"source": core_devices[0], "target": edge_id, "type": "edge"})
    
    # Connect different locations through their first core device
    locations = list(location_groups.keys())
    for i in range(len(locations) - 1):
        loc1_core = location_groups[locations[i]]["core"]
        loc2_core = location_groups[locations[i + 1]]["core"]
        if loc1_core and loc2_core:
            links.append({"source": loc1_core[0], "target": loc2_core[0], "type": "wan"})
    
    return {"nodes": nodes, "links": links}

# ===================== SSH ROUTES =====================
class SSHConnectionRequest(BaseModel):
    device_id: str
    username: str
    password: str
    command: Optional[str] = None

class SSHCommandRequest(BaseModel):
    device_id: str
    username: str
    password: str
    command: str

@ssh_router.post("/connect")
async def ssh_connect(request: SSHConnectionRequest, current_user: dict = Depends(get_current_user)):
    """Test SSH connection to a device"""
    device = await db.devices.find_one({"id": request.device_id}, {"_id": 0})
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    try:
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh_client.connect(
            hostname=device["ip_address"],
            username=request.username,
            password=request.password,
            timeout=10
        )
        ssh_client.close()
        return {"success": True, "message": f"Successfully connected to {device['name']}"}
    except paramiko.AuthenticationException:
        raise HTTPException(status_code=401, detail="Authentication failed")
    except paramiko.SSHException as e:
        raise HTTPException(status_code=500, detail=f"SSH error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Connection error: {str(e)}")

@ssh_router.post("/execute")
async def ssh_execute_command(request: SSHCommandRequest, current_user: dict = Depends(get_current_user)):
    """Execute a command on a device via SSH"""
    device = await db.devices.find_one({"id": request.device_id}, {"_id": 0})
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    try:
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh_client.connect(
            hostname=device["ip_address"],
            username=request.username,
            password=request.password,
            timeout=10
        )
        
        stdin, stdout, stderr = ssh_client.exec_command(request.command, timeout=30)
        output = stdout.read().decode('utf-8')
        error = stderr.read().decode('utf-8')
        ssh_client.close()
        
        return {
            "success": True,
            "output": output,
            "error": error,
            "device": device["name"]
        }
    except paramiko.AuthenticationException:
        raise HTTPException(status_code=401, detail="Authentication failed")
    except paramiko.SSHException as e:
        raise HTTPException(status_code=500, detail=f"SSH error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Connection error: {str(e)}")

# ===================== NOTIFICATION ROUTES =====================
class NotificationSettings(BaseModel):
    email_enabled: bool = False
    email_address: Optional[str] = None
    p1_notify: bool = True
    p2_notify: bool = True
    critical_alerts: bool = True

@notifications_router.get("/settings")
async def get_notification_settings(current_user: dict = Depends(get_current_user)):
    """Get user notification settings"""
    settings = await db.notification_settings.find_one({"user_id": current_user["id"]}, {"_id": 0})
    if not settings:
        settings = {
            "user_id": current_user["id"],
            "email_enabled": False,
            "email_address": current_user.get("email"),
            "p1_notify": True,
            "p2_notify": True,
            "critical_alerts": True
        }
    return settings

@notifications_router.post("/settings")
async def update_notification_settings(settings: NotificationSettings, current_user: dict = Depends(get_current_user)):
    """Update user notification settings"""
    settings_dict = settings.model_dump()
    settings_dict["user_id"] = current_user["id"]
    settings_dict["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    await db.notification_settings.update_one(
        {"user_id": current_user["id"]},
        {"$set": settings_dict},
        upsert=True
    )
    return {"message": "Settings updated"}

@notifications_router.get("/history")
async def get_notification_history(limit: int = 50, current_user: dict = Depends(get_current_user)):
    """Get notification history"""
    notifications = await db.notifications.find(
        {"user_id": current_user["id"]},
        {"_id": 0}
    ).sort("created_at", -1).to_list(limit)
    return notifications

# Helper function to send notifications
async def send_notification(title: str, message: str, severity: str, incident_id: Optional[str] = None):
    """Send notification via WebSocket and store in DB"""
    notification = {
        "id": str(uuid.uuid4()),
        "title": title,
        "message": message,
        "severity": severity,
        "incident_id": incident_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "read": False
    }
    
    # Broadcast to all connected WebSocket clients
    await ws_manager.broadcast({
        "type": "notification",
        "data": notification
    })
    
    # Store notification for all users (in production, filter by settings)
    users = await db.users.find({}, {"_id": 0, "id": 1}).to_list(100)
    for user in users:
        user_notification = {**notification, "user_id": user["id"]}
        await db.notifications.insert_one(user_notification)
    
    return notification

# ===================== AGENT ROUTES =====================
@agents_router.get("")
async def get_agents(current_user: dict = Depends(get_current_user)):
    """Get all agents"""
    agents = await db.agents.find({}, {"_id": 0}).to_list(100)
    return agents

@agents_router.get("/{agent_id}")
async def get_agent(agent_id: str, current_user: dict = Depends(get_current_user)):
    """Get agent by ID"""
    agent = await db.agents.find_one({"id": agent_id}, {"_id": 0})
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent

@agents_router.post("")
async def create_agent(agent_data: AgentCreate, current_user: dict = Depends(get_current_user)):
    """Create a new agent with activation code"""
    # Verify activation code
    activation = await db.activation_codes.find_one({"code": agent_data.activation_code, "status": "available"})
    if not activation:
        raise HTTPException(status_code=400, detail="Invalid or already used activation code")
    
    # Create agent
    agent = Agent(
        name=agent_data.name,
        description=agent_data.description,
        activation_code=agent_data.activation_code,
        created_by=current_user["name"]
    )
    
    agent_dict = agent.model_dump()
    agent_dict["created_at"] = agent_dict["created_at"].isoformat()
    agent_dict["updated_at"] = agent_dict["updated_at"].isoformat()
    await db.agents.insert_one(agent_dict)
    
    # Mark activation code as used
    await db.activation_codes.update_one(
        {"code": agent_data.activation_code},
        {"$set": {
            "status": "activated",
            "activated_at": datetime.now(timezone.utc).isoformat(),
            "activated_by": current_user["name"],
            "agent_id": agent.id
        }}
    )
    
    return agent

@agents_router.put("/{agent_id}")
async def update_agent(agent_id: str, agent_data: AgentUpdate, current_user: dict = Depends(get_current_user)):
    """Update agent"""
    agent = await db.agents.find_one({"id": agent_id})
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    update_data = {k: v for k, v in agent_data.model_dump().items() if v is not None}
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    await db.agents.update_one({"id": agent_id}, {"$set": update_data})
    updated = await db.agents.find_one({"id": agent_id}, {"_id": 0})
    return updated

@agents_router.post("/{agent_id}/assign-device/{device_id}")
async def assign_device_to_agent(agent_id: str, device_id: str, current_user: dict = Depends(get_current_user)):
    """Assign a device to an agent"""
    agent = await db.agents.find_one({"id": agent_id})
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    device = await db.devices.find_one({"id": device_id})
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    assigned_devices = agent.get("assigned_devices", [])
    if len(assigned_devices) >= 15:
        raise HTTPException(status_code=400, detail="Agent has reached maximum device limit (15). Please activate a new agent.")
    
    if device_id in assigned_devices:
        raise HTTPException(status_code=400, detail="Device already assigned to this agent")
    
    assigned_devices.append(device_id)
    await db.agents.update_one(
        {"id": agent_id},
        {"$set": {"assigned_devices": assigned_devices, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    # Update device with agent reference
    await db.devices.update_one({"id": device_id}, {"$set": {"agent_id": agent_id}})
    
    return {"message": f"Device {device['name']} assigned to agent {agent['name']}", "total_devices": len(assigned_devices)}

@agents_router.post("/{agent_id}/unassign-device/{device_id}")
async def unassign_device_from_agent(agent_id: str, device_id: str, current_user: dict = Depends(get_current_user)):
    """Unassign a device from an agent"""
    agent = await db.agents.find_one({"id": agent_id})
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    assigned_devices = agent.get("assigned_devices", [])
    if device_id not in assigned_devices:
        raise HTTPException(status_code=400, detail="Device not assigned to this agent")
    
    assigned_devices.remove(device_id)
    await db.agents.update_one(
        {"id": agent_id},
        {"$set": {"assigned_devices": assigned_devices, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    await db.devices.update_one({"id": device_id}, {"$unset": {"agent_id": ""}})
    
    return {"message": "Device unassigned", "total_devices": len(assigned_devices)}

# ===================== ACTIVATION CODE ROUTES =====================
@api_router.get("/activation-codes")
async def get_activation_codes(status: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    """Get activation codes"""
    query = {}
    if status:
        query["status"] = status
    codes = await db.activation_codes.find(query, {"_id": 0}).to_list(1000)
    return codes

@api_router.post("/activation-codes/generate")
async def generate_codes(count: int = 200, current_user: dict = Depends(get_current_user)):
    """Generate new activation codes"""
    if current_user.get("role") not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Only admins can generate activation codes")
    
    codes = generate_activation_codes(count)
    await db.activation_codes.insert_many(codes)
    
    return {"message": f"Generated {count} activation codes", "codes": [c["code"] for c in codes]}

@api_router.post("/activation-codes/verify")
async def verify_activation_code(code: str):
    """Verify if an activation code is valid"""
    activation = await db.activation_codes.find_one({"code": code}, {"_id": 0})
    if not activation:
        return {"valid": False, "message": "Invalid activation code"}
    if activation["status"] != "available":
        return {"valid": False, "message": f"Activation code already {activation['status']}"}
    return {"valid": True, "message": "Activation code is valid"}

# ===================== SNMP ROUTES =====================
class SNMPDiscoveryRequest(BaseModel):
    ip_range: str  # e.g., "192.168.1.0/24" or "192.168.1.1-192.168.1.50"
    community: str = "public"
    port: int = 161
    timeout: int = 2

class SNMPPollRequest(BaseModel):
    ip_address: str
    community: str = "public"
    oids: List[str] = ["1.3.6.1.2.1.1.1.0", "1.3.6.1.2.1.1.5.0"]  # sysDescr, sysName

@snmp_router.post("/discover")
async def snmp_discover(request: SNMPDiscoveryRequest, current_user: dict = Depends(get_current_user)):
    """Discover devices via SNMP (simulated for demo)"""
    # In production, this would perform actual SNMP discovery
    # For demo purposes, we simulate discovery
    discovered = []
    
    # Simulate discovered devices
    demo_devices = [
        {"ip": "192.168.1.1", "name": "Gateway-Router", "type": "router", "vendor": "Cisco"},
        {"ip": "192.168.1.2", "name": "Core-Switch-1", "type": "switch", "vendor": "Cisco"},
        {"ip": "192.168.1.10", "name": "File-Server", "type": "server", "vendor": "Dell"},
    ]
    
    for device in demo_devices:
        discovered.append({
            "ip_address": device["ip"],
            "name": device["name"],
            "type": device["type"],
            "vendor": device["vendor"],
            "snmp_reachable": True,
            "community": request.community
        })
    
    return {"discovered_count": len(discovered), "devices": discovered}

@snmp_router.post("/poll")
async def snmp_poll(request: SNMPPollRequest, current_user: dict = Depends(get_current_user)):
    """Poll device via SNMP (simulated for demo)"""
    # Simulated SNMP poll response
    return {
        "ip_address": request.ip_address,
        "community": request.community,
        "results": {
            "1.3.6.1.2.1.1.1.0": "Cisco IOS Software, Version 15.1(4)M4",
            "1.3.6.1.2.1.1.5.0": "Core-Router-01",
            "1.3.6.1.2.1.1.3.0": "4532112",  # sysUpTime
        }
    }

@snmp_router.post("/add-discovered")
async def add_discovered_device(device_data: dict, current_user: dict = Depends(get_current_user)):
    """Add a discovered SNMP device"""
    device = Device(
        name=device_data.get("name", "Unknown"),
        type=DeviceType(device_data.get("type", "server")),
        ip_address=device_data.get("ip_address"),
        location=device_data.get("location", "Discovered"),
        vendor=device_data.get("vendor"),
        tags=["snmp-discovered"]
    )
    
    device_dict = device.model_dump()
    device_dict["created_at"] = device_dict["created_at"].isoformat()
    device_dict["last_seen"] = device_dict["last_seen"].isoformat()
    await db.devices.insert_one(device_dict)
    
    return device

# ===================== TELNET ROUTES =====================
class TelnetRequest(BaseModel):
    device_id: str
    username: str
    password: str
    command: Optional[str] = None

@telnet_router.post("/connect")
async def telnet_connect(request: TelnetRequest, current_user: dict = Depends(get_current_user)):
    """Test Telnet connection to a device"""
    device = await db.devices.find_one({"id": request.device_id}, {"_id": 0})
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    # For demo, simulate connection
    # In production, use telnetlib3 for actual connection
    return {
        "success": True,
        "message": f"Telnet connection to {device['name']} ({device['ip_address']}) simulated",
        "note": "Actual telnet requires network access to device"
    }

@telnet_router.post("/execute")
async def telnet_execute(request: TelnetRequest, current_user: dict = Depends(get_current_user)):
    """Execute command via Telnet"""
    device = await db.devices.find_one({"id": request.device_id}, {"_id": 0})
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    # Simulated response
    return {
        "success": True,
        "device": device["name"],
        "command": request.command,
        "output": f"Simulated output for command: {request.command}\nDevice: {device['name']}\nIP: {device['ip_address']}",
        "note": "Actual telnet execution requires network access"
    }

# ===================== ESCALATION ROUTES =====================
@escalation_router.get("/contacts")
async def get_escalation_contacts(current_user: dict = Depends(get_current_user)):
    """Get all escalation contacts"""
    contacts = await db.escalation_contacts.find({}, {"_id": 0}).to_list(100)
    return contacts

@escalation_router.post("/contacts")
async def create_escalation_contact(contact_data: EscalationContactCreate, current_user: dict = Depends(get_current_user)):
    """Create escalation contact"""
    contact = EscalationContact(**contact_data.model_dump())
    contact_dict = contact.model_dump()
    contact_dict["created_at"] = contact_dict["created_at"].isoformat()
    await db.escalation_contacts.insert_one(contact_dict)
    return contact

@escalation_router.delete("/contacts/{contact_id}")
async def delete_escalation_contact(contact_id: str, current_user: dict = Depends(get_current_user)):
    """Delete escalation contact"""
    result = await db.escalation_contacts.delete_one({"id": contact_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Contact not found")
    return {"message": "Contact deleted"}

@escalation_router.get("/levels")
async def get_escalation_levels():
    """Get escalation level configuration"""
    return ESCALATION_LEVELS

@escalation_router.post("/check")
async def check_escalations(current_user: dict = Depends(get_current_user)):
    """Check for incidents/alerts that need escalation"""
    now = datetime.now(timezone.utc)
    escalations_needed = []
    
    # Get open P1/P2 incidents
    incidents = await db.incidents.find({
        "priority": {"$in": ["P1", "P2"]},
        "status": {"$in": ["open", "in_progress"]}
    }, {"_id": 0}).to_list(100)
    
    for incident in incidents:
        created_at = datetime.fromisoformat(incident["created_at"].replace("Z", "+00:00"))
        hours_open = (now - created_at).total_seconds() / 3600
        
        for level in ESCALATION_LEVELS:
            if hours_open >= level["threshold_hours"] and incident["priority"] in level["priority_filter"]:
                # Check if already escalated to this level
                existing = await db.escalation_history.find_one({
                    "incident_id": incident["id"],
                    "level": level["level"]
                })
                
                if not existing:
                    escalations_needed.append({
                        "incident": incident,
                        "level": level,
                        "hours_open": round(hours_open, 1)
                    })
    
    return {"escalations_needed": escalations_needed, "count": len(escalations_needed)}

@escalation_router.post("/send")
async def send_escalation_email(incident_id: str, level: int, current_user: dict = Depends(get_current_user)):
    """Send escalation email"""
    incident = await db.incidents.find_one({"id": incident_id}, {"_id": 0})
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    
    # Get contacts for this level
    contacts = await db.escalation_contacts.find({"level": level}, {"_id": 0}).to_list(10)
    if not contacts:
        raise HTTPException(status_code=400, detail=f"No escalation contacts configured for level {level}")
    
    level_info = next((l for l in ESCALATION_LEVELS if l["level"] == level), None)
    
    # Create email content
    subject = f"[ESCALATION - {level_info['name']}] {incident['priority']} Incident: {incident['title']}"
    body = f"""
    <html>
    <body>
    <h2>ATECH NOC Commander - Escalation Notice</h2>
    <p><strong>This incident requires immediate attention.</strong></p>
    
    <table style="border-collapse: collapse; width: 100%; max-width: 600px;">
        <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Ticket:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{incident['ticket_number']}</td></tr>
        <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Priority:</strong></td><td style="padding: 8px; border: 1px solid #ddd; color: {'red' if incident['priority'] == 'P1' else 'orange'};">{incident['priority']}</td></tr>
        <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Title:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{incident['title']}</td></tr>
        <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Description:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{incident['description']}</td></tr>
        <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Status:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{incident['status']}</td></tr>
        <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Created:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{incident['created_at']}</td></tr>
        <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Escalation Level:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{level_info['name']}</td></tr>
    </table>
    
    <p style="margin-top: 20px;">Please take immediate action on this incident.</p>
    <p>- ATECH NOC Commander</p>
    </body>
    </html>
    """
    
    # Record escalation
    escalation_record = {
        "id": str(uuid.uuid4()),
        "incident_id": incident_id,
        "level": level,
        "level_name": level_info["name"],
        "contacts": [c["email"] for c in contacts],
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "sent_by": current_user["name"]
    }
    await db.escalation_history.insert_one(escalation_record)
    
    # Update incident
    await db.incidents.update_one(
        {"id": incident_id},
        {"$set": {"escalation_level": level, "last_escalated": datetime.now(timezone.utc).isoformat()}}
    )
    
    # In production, send actual email via Office 365
    # For demo, we simulate
    email_sent = False
    if SMTP_USERNAME and SMTP_PASSWORD:
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = EMAIL_FROM
            msg['To'] = ', '.join([c["email"] for c in contacts])
            msg.attach(MIMEText(body, 'html'))
            
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                server.starttls()
                server.login(SMTP_USERNAME, SMTP_PASSWORD)
                server.send_message(msg)
            email_sent = True
        except Exception as e:
            logger.error(f"Failed to send escalation email: {e}")
    
    return {
        "message": "Escalation recorded",
        "email_sent": email_sent,
        "recipients": [c["email"] for c in contacts],
        "level": level_info["name"]
    }

# Include all routers
api_router.include_router(auth_router)
api_router.include_router(devices_router)
api_router.include_router(alerts_router)
api_router.include_router(incidents_router)
api_router.include_router(performance_router)
api_router.include_router(assets_router)
api_router.include_router(reports_router)
api_router.include_router(config_router)
api_router.include_router(sla_router)
api_router.include_router(ai_router)
api_router.include_router(dashboard_router)
api_router.include_router(topology_router)
api_router.include_router(ssh_router)
api_router.include_router(notifications_router)
api_router.include_router(agents_router)
api_router.include_router(snmp_router)
api_router.include_router(telnet_router)
api_router.include_router(escalation_router)

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
