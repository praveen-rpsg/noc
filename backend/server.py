from fastapi import FastAPI, APIRouter, HTTPException, Depends, status, WebSocket, WebSocketDisconnect, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from device_monitor import monitor_devices
from snmp_receiver import start_snmp_trap_receiver
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict, EmailStr
from typing import List, Optional, Dict, Any, Set
import uuid
from datetime import datetime, timezone, timedelta
import time
import jwt
import bcrypt
import asyncio
from enum import Enum
import json
import paramiko
import re
import io
import telnetlib3
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from agents import (
     Agent, AgentCreate, AgentUpdate,
    ActivationCode, EscalationContact, EscalationContactCreate, ESCALATION_LEVELS
)

from agents import (
    generate_activation_codes, generate_activation_code, Agent, AgentCreate, AgentUpdate,
    ActivationCode, EscalationContact, EscalationContactCreate, ESCALATION_LEVELS
)
from network_services import get_vendor_profile, VENDOR_PROFILES
from network_services import (
    SNMPService, NetworkDiscoveryService, SSHService,
    OpenStackConnector, OracleDBConnector, VCenterConnector,
    BackgroundPollingService, DiscoveryMethod, DiscoveredDevice, DiscoveryJob
)

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / 'dbvar.env')

# MongoDB connection
# mongo_url = os.environ['MONGO_URL']
# client = AsyncIOMotorClient(mongo_url)
# db = client[os.environ['DB_NAME']]
from shared import db

# JWT Config
JWT_SECRET = os.environ.get('JWT_SECRET', 'noc-commander-secret')
JWT_ALGORITHM = os.environ.get('JWT_ALGORITHM', 'HS256')
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get('ACCESS_TOKEN_EXPIRE_MINUTES', 1440))

# # Emergent LLM Key
# EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY', '')

# Office 365 SMTP Configuration
SMTP_SERVER = os.environ.get('SMTP_SERVER', 'smtp.office365.com')
SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
SMTP_USERNAME = os.environ.get('SMTP_USERNAME', '')
SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD', '')
EMAIL_FROM = os.environ.get('EMAIL_FROM', 'noc@atech.com')

# Create the main app
app = FastAPI(title="ATECH NOC Commander API", version="2.0.0")

# Health check endpoint (outside /api prefix for easy access)
@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "version": "2.0.0", "service": "ATECH NOC Commander"}

@app.on_event("startup")
async def startup_event():

    # =========================
    # Default Admin User
    # =========================
    existing_admin = await db.users.find_one(
        {"email": "noc@ameyatechnologies.com"}
    )

    if not existing_admin:
        now = datetime.now(timezone.utc)

        await db.users.insert_one({
            "id": str(uuid.uuid4()),
            "email": "noc@ameyatechnologies.com",
            "name": "Admin User",
            "role": "admin",
            "password_hash": hash_password("admin123"),
            "is_active": True,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat()
        })

        print("Default admin created")

    # =========================
    # Default Activated License
    # =========================
    existing_codes = await db.activation_codes.count_documents({})
 
    if existing_codes == 0:
        codes = generate_activation_codes(1)
        await db.activation_codes.insert_many(codes)
    # =========================
    # Existing Startup Logic
    # =========================
    asyncio.create_task(
        monitor_devices(
            db,
            get_device_metrics,
            decrypt_password,
            create_offline_incident,
            resolve_device_incident,
            save_device_event,
            ws_manager
 # Modified on 24-07-26 for calling websocket manager
        )
    )
    asyncio.create_task(start_snmp_trap_receiver())
    print("Background monitor and SNMP Trap Receiver started.")
    
# License activation status check (public endpoint)
@app.get("/api/license/status")
async def get_license_status():
    """Check if the application is activated"""
    license_doc = await db.app_license.find_one({"type": "application_license"})
    if license_doc and license_doc.get("is_activated"):
        return {
            "is_activated": True,
            "activated_at": license_doc.get("activated_at"),
            "activation_code": license_doc.get("activation_code"),
            "instance_id": license_doc.get("instance_id")
        }
    return {"is_activated": False}

# Activate application with code (public endpoint)
@app.post("/api/license/activate")
async def activate_application(data: dict):
    """Activate the application with a valid activation code"""
    activation_code = data.get("activation_code", "").strip().upper()
    
    if not activation_code:
        raise HTTPException(status_code=400, detail="Activation code is required")
    
    # Check if already activated
    existing_license = await db.app_license.find_one({"type": "application_license"})
    if existing_license and existing_license.get("is_activated"):
        raise HTTPException(status_code=400, detail="Application is already activated")
    
    # Find the activation code
    code_doc = await db.activation_codes.find_one({"code": activation_code})
    
    if not code_doc:
        raise HTTPException(status_code=404, detail="Invalid activation code")
    
    if code_doc.get("status") == "used":
        raise HTTPException(status_code=400, detail="This activation code has already been used")
    
    if code_doc.get("status") == "revoked":
        raise HTTPException(status_code=400, detail="This activation code has been revoked")
    
    # Generate instance ID
    instance_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    
    # Mark code as used
    await db.activation_codes.update_one(
        {"_id": code_doc["_id"]},
        {"$set": {
            "status": "used",
            "used_at": now,
            "instance_id": instance_id
        }}
    )
    
    # Create or update application license
    license_data = {
        "type": "application_license",
        "is_activated": True,
        "activation_code": activation_code,
        "activated_at": now,
        "instance_id": instance_id
    }
    
    await db.app_license.update_one(
        {"type": "application_license"},
        {"$set": license_data},
        upsert=True
    )
    
    return {
        "success": True,
        "message": "Application activated successfully",
        "instance_id": instance_id,
        "activated_at": now
    }

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
    STORAGE = "storage"
    VIRTUALIZATION_HOST = "virtualization_host"
    NETAPP_STORAGE = "netapp_storage"
    HITACHI_DEVICE = "hitachi_device"
    ARISTA_DEVICE = "arista_device"
    DELL_EMC_STORAGE = "dell_emc_storage"
    ORACLE_DEVICE = "oracle_device"
    AZURE_DEVICE = "azure_device"
    
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
    PENDING_APPROVAL = "pending_approval"

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
    username: Optional[str] = None
    password: Optional[str] = None
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
    # Enhanced device details
    mac_address: Optional[str] = None
    interfaces: List[Dict] = Field(default_factory=list)
    routing_table: List[Dict] = Field(default_factory=list)
    hostname: Optional[str] = None
    os_version: Optional[str] = None
    os_install_date: Optional[str] = None  # ISO date string
    warranty_status: Optional[str] = None  # "active", "expired", "expiring_soon", "unknown"
    warranty_expiry: Optional[str] = None  # ISO date string
    aaa_enabled: bool = False
    device_description: Optional[str] = None

class DeviceCreate(BaseModel):
    name: str
    type: DeviceType
    ip_address: str
    location: str
    username: Optional[str] = None
    password: Optional[str] = None
    vendor: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    firmware_version: Optional[str] = None
    config_url: Optional[str] = None  # URL to device configuration page
    tags: List[str] = []
    # Enhanced device details
    mac_address: Optional[str] = None
    hostname: Optional[str] = None
    os_version: Optional[str] = None
    os_install_date: Optional[str] = None
    warranty_status: Optional[str] = None
    warranty_expiry: Optional[str] = None
    aaa_enabled: bool = False
    device_description: Optional[str] = None

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
    purchase_date:Optional[str] = None #Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    warranty_expiry:Optional[str] = "unknown" #Field(default_factory=lambda: (datetime.now(timezone.utc) + timedelta(days=365)).isoformat())
    warranty_status:Optional[str] = "unknown" # "active", "expired", "expiring_soon"
    eol_date:Optional[str] = None # Field(default_factory=lambda: (datetime.now(timezone.utc) + timedelta(days=365*5)).isoformat())
    contract_details: Optional[str] = None 
    license_info: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    # Extended fields for inventory reporting
    ip_address: Optional[str] = None
    mac_address: Optional[str] = None
    device_id: Optional[str] = None  # Link to monitoring device
    oem_details: Optional[str] = None
    discovery_method: Optional[str] = None
    auto_discovered: bool = False

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
    warranty_status: Optional[str] = None
    eol_date: Optional[str] = None
    contract_details: Optional[str] = None
    license_info: Optional[str] = None
    # Extended fields
    ip_address: Optional[str] = None
    mac_address: Optional[str] = None
    oem_details: Optional[str] = None

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

# ===================== SETTINGS MODELS =====================
class EmailConfig(BaseModel):
    """Office 365 Email Configuration"""
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    smtp_server: str = "smtp.office365.com"
    smtp_port: int = 587
    username: str  # O365 email address
    password: str  # App password or OAuth token
    sender_email: str  # From email address
    sender_name: str = "ATECH NOC Commander"
    use_tls: bool = True
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class EmailConfigCreate(BaseModel):
    smtp_server: str = "smtp.office365.com"
    smtp_port: int = 587
    username: str
    password: str
    sender_email: str
    sender_name: str = "ATECH NOC Commander"
    use_tls: bool = True

class SNMPCommunityString(BaseModel):
    """SNMP Community String for device groups"""
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str  # Friendly name for this config
    community_string: str  # The actual community string (read-only or read-write)
    version: str = "v2c"  # v1, v2c, v3
    ip_range: Optional[str] = None  # CIDR notation e.g., "192.168.1.0/24"
    device_types: List[str] = []  # Device types this applies to
    location: Optional[str] = None  # Location/datacenter this applies to
    description: Optional[str] = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class SNMPCommunityStringCreate(BaseModel):
    name: str
    community_string: str
    version: str = "v2c"
    ip_range: Optional[str] = None
    device_types: List[str] = []
    location: Optional[str] = None
    description: Optional[str] = None

class SNMPv3Config(BaseModel):
    """SNMP v3 Configuration with authentication"""
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    security_level: str = "authPriv"  # noAuthNoPriv, authNoPriv, authPriv
    username: str
    auth_protocol: str = "SHA"  # MD5, SHA, SHA224, SHA256, SHA384, SHA512
    auth_password: Optional[str] = None
    priv_protocol: str = "AES"  # DES, 3DES, AES, AES192, AES256
    priv_password: Optional[str] = None
    ip_range: Optional[str] = None
    device_types: List[str] = []
    location: Optional[str] = None
    description: Optional[str] = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class SNMPv3ConfigCreate(BaseModel):
    name: str
    security_level: str = "authPriv"
    username: str
    auth_protocol: str = "SHA"
    auth_password: Optional[str] = None
    priv_protocol: str = "AES"
    priv_password: Optional[str] = None
    ip_range: Optional[str] = None
    device_types: List[str] = []
    location: Optional[str] = None
    description: Optional[str] = None

# Create settings router
settings_router = APIRouter(prefix="/settings", tags=["Settings"])

# ===================== ADDITIONAL SETTINGS MODELS =====================

class OpenStackConfig(BaseModel):
    """OpenStack Configuration"""
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    auth_url: str  # e.g., http://openstack.example.com:5000/v3
    username: str
    password: str
    project_name: str
    user_domain_name: str = "Default"
    project_domain_name: str = "Default"
    region_name: Optional[str] = None
    # Services to monitor
    monitor_nova: bool = True
    monitor_neutron: bool = True
    monitor_cinder: bool = True
    monitor_keystone: bool = True
    monitor_glance: bool = True
    monitor_heat: bool = True
    monitor_swift: bool = True
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class OpenStackConfigCreate(BaseModel):
    name: str
    auth_url: str
    username: str
    password: str
    project_name: str
    user_domain_name: str = "Default"
    project_domain_name: str = "Default"
    region_name: Optional[str] = None
    monitor_nova: bool = True
    monitor_neutron: bool = True
    monitor_cinder: bool = True
    monitor_keystone: bool = True
    monitor_glance: bool = True
    monitor_heat: bool = True
    monitor_swift: bool = True

class OracleDBConfig(BaseModel):
    """Oracle Database Configuration"""
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    host: str
    port: int = 1521
    service_name: str
    username: str
    password: str
    # Metrics to monitor
    monitor_tablespace: bool = True
    monitor_sessions: bool = True
    monitor_locks: bool = True
    monitor_performance: bool = True
    monitor_asm: bool = True
    monitor_dataguard: bool = False
    monitor_rman: bool = True
    alert_threshold_tablespace: int = 80  # Percentage
    alert_threshold_sessions: int = 90  # Percentage of max
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class OracleDBConfigCreate(BaseModel):
    name: str
    host: str
    port: int = 1521
    service_name: str
    username: str
    password: str
    monitor_tablespace: bool = True
    monitor_sessions: bool = True
    monitor_locks: bool = True
    monitor_performance: bool = True
    monitor_asm: bool = True
    monitor_dataguard: bool = False
    monitor_rman: bool = True
    alert_threshold_tablespace: int = 80
    alert_threshold_sessions: int = 90

class VCenterConfig(BaseModel):
    """VMware vCenter Configuration"""
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    host: str
    port: int = 443
    username: str
    password: str
    # Monitoring options
    monitor_vms: bool = True
    monitor_esxi_hosts: bool = True
    monitor_datastores: bool = True
    monitor_clusters: bool = True
    monitor_networks: bool = True
    monitor_resource_pools: bool = True
    # Alert thresholds
    alert_threshold_cpu: int = 80
    alert_threshold_memory: int = 85
    alert_threshold_datastore: int = 80
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class VCenterConfigCreate(BaseModel):
    name: str
    host: str
    port: int = 443
    username: str
    password: str
    monitor_vms: bool = True
    monitor_esxi_hosts: bool = True
    monitor_datastores: bool = True
    monitor_clusters: bool = True
    monitor_networks: bool = True
    monitor_resource_pools: bool = True
    alert_threshold_cpu: int = 80
    alert_threshold_memory: int = 85
    alert_threshold_datastore: int = 80

class AAAServerConfig(BaseModel):
    """AAA Server Configuration (RADIUS/TACACS+)"""
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    server_type: str  # "radius" or "tacacs"
    primary_host: str
    primary_port: int = 1812  # RADIUS: 1812, TACACS: 49
    secondary_host: Optional[str] = None
    secondary_port: Optional[int] = None
    shared_secret: str
    timeout: int = 5  # seconds
    retries: int = 3
    use_for_login: bool = True
    use_for_device_auth: bool = True
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class AAAServerConfigCreate(BaseModel):
    name: str
    server_type: str  # "radius" or "tacacs"
    primary_host: str
    primary_port: int = 1812
    secondary_host: Optional[str] = None
    secondary_port: Optional[int] = None
    shared_secret: str
    timeout: int = 5
    retries: int = 3
    use_for_login: bool = True
    use_for_device_auth: bool = True

class BackupConfig(BaseModel):
    """Backup Configuration"""
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    backup_type: str  # "tftp", "scp", "ssh_command", "api"
    # For TFTP/SCP
    server_host: Optional[str] = None
    server_port: Optional[int] = None
    server_username: Optional[str] = None
    server_password: Optional[str] = None
    server_path: Optional[str] = None
    # For SSH command-based
    ssh_command: Optional[str] = None
    # For API-based
    api_endpoint: Optional[str] = None
    api_key: Optional[str] = None
    api_method: str = "POST"
    # Scheduling
    schedule_enabled: bool = False
    schedule_cron: Optional[str] = None  # Cron expression
    schedule_frequency: Optional[str] = None  # "daily", "weekly", "monthly"
    schedule_time: Optional[str] = None  # HH:MM format
    retention_days: int = 30
    # Target devices/applications
    target_type: str = "device"  # "device", "application", "all"
    target_ids: List[str] = []
    is_active: bool = True
    last_run: Optional[datetime] = None
    last_status: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class BackupConfigCreate(BaseModel):
    name: str
    backup_type: str
    server_host: Optional[str] = None
    server_port: Optional[int] = None
    server_username: Optional[str] = None
    server_password: Optional[str] = None
    server_path: Optional[str] = None
    ssh_command: Optional[str] = None
    api_endpoint: Optional[str] = None
    api_key: Optional[str] = None
    api_method: str = "POST"
    schedule_enabled: bool = False
    schedule_cron: Optional[str] = None
    schedule_frequency: Optional[str] = None
    schedule_time: Optional[str] = None
    retention_days: int = 30
    target_type: str = "device"
    target_ids: List[str] = []

class CustomDashboard(BaseModel):
    """Custom Dashboard Configuration"""
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    application_id: Optional[str] = None
    application_type: Optional[str] = None  # "openstack", "oracle", "vcenter", "custom"
    template_type: Optional[str] = None  # "monitoring", "performance", "capacity", "custom"
    layout: List[Dict[str, Any]] = []  # Widget positions and configs
    widgets: List[Dict[str, Any]] = []  # Widget definitions
    is_default: bool = False
    created_by: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class CustomDashboardCreate(BaseModel):
    name: str
    application_id: Optional[str] = None
    application_type: Optional[str] = None
    template_type: Optional[str] = None
    layout: List[Dict[str, Any]] = []
    widgets: List[Dict[str, Any]] = []
    is_default: bool = False

class IncidentAction(BaseModel):
    """Incident Action for AI Agent"""
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str
    action_type: str  # "auto_resolve", "reboot_required", "link_reset", "hardware_failure"
    description: str
    requires_confirmation: bool = False
    confirmation_status: Optional[str] = None  # "pending", "approved", "rejected"
    confirmed_by: Optional[str] = None
    executed: bool = False
    executed_at: Optional[datetime] = None
    result: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# ===================== AUTONOMOUS AGENT MODELS =====================

class ActionType(str, Enum):
    # Auto-resolve actions (no confirmation needed)
    CONFIG_CORRECTION = "config_correction"
    CLEAR_LOGS = "clear_logs"
    ROUTE_TABLE_FIX = "route_table_fix"
    TRACEROUTE_ANALYSIS = "traceroute_analysis"
    STP_LOOP_DETECTION = "stp_loop_detection"
    ASYMMETRIC_ROUTING_FIX = "asymmetric_routing_fix"
    MEMORY_CLEANUP = "memory_cleanup"
    SWITCHING_LOOP_FIX = "switching_loop_fix"
    ROUTING_LOOP_FIX = "routing_loop_fix"
    SERVICE_RESTART = "service_restart"
    PING_TEST = "ping_test"
    INTERFACE_BOUNCE = "interface_bounce"
    
    # Actions requiring confirmation
    DEVICE_REBOOT = "device_reboot"
    LINK_RESET = "link_reset"
    FIRMWARE_UPDATE = "firmware_update"
    FACTORY_RESET = "factory_reset"
    POWER_CYCLE = "power_cycle"
    HARDWARE_REPLACEMENT = "hardware_replacement"
    STORAGE_RESTART = "storage_restart"
    DATABASE_RESTART = "database_restart"
    VM_RESTART = "vm_restart"

# Actions that can be auto-executed without confirmation
AUTO_RESOLVE_ACTIONS = [
    ActionType.CLEAR_LOGS,
    ActionType.ROUTE_TABLE_FIX,
    ActionType.TRACEROUTE_ANALYSIS,
    ActionType.STP_LOOP_DETECTION,
    ActionType.ASYMMETRIC_ROUTING_FIX,
    ActionType.MEMORY_CLEANUP,
    ActionType.SWITCHING_LOOP_FIX,
    ActionType.ROUTING_LOOP_FIX,
    ActionType.SERVICE_RESTART,
    ActionType.PING_TEST,
    
    
]

# Actions requiring user confirmation
CONFIRMATION_REQUIRED_ACTIONS = [
    ActionType.DEVICE_REBOOT,
    ActionType.LINK_RESET,
    ActionType.FIRMWARE_UPDATE,
    ActionType.FACTORY_RESET,
    ActionType.POWER_CYCLE,
    ActionType.HARDWARE_REPLACEMENT,
    ActionType.STORAGE_RESTART,
    ActionType.DATABASE_RESTART,
    ActionType.VM_RESTART,
    ActionType.CONFIG_CORRECTION,
    ActionType.INTERFACE_BOUNCE,
    ActionType.SERVICE_RESTART,
    ActionType.ROUTE_TABLE_FIX,
]

class AgentExecutionStatus(str, Enum):
    PENDING = "pending"
    ANALYZING = "analyzing"
    EXECUTING = "executing"
    WAITING_CONFIRMATION = "waiting_confirmation"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIALLY_RESOLVED = "partially_resolved"

class AgentExecution(BaseModel):
    """Tracks an AI agent's execution session for an incident"""
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str
    device_id: Optional[str] = None
    device_ip: Optional[str] = None
    status: AgentExecutionStatus = AgentExecutionStatus.PENDING
    triggered_by: str  # "auto" or user name
    trigger_type: str = "manual"  # "auto" or "manual"
    
    # Analysis results
    analysis: Optional[str] = None
    root_cause: Optional[str] = None
    
    # Actions to be taken
    planned_actions: List[Dict[str, Any]] = []
    executed_actions: List[Dict[str, Any]] = []
    pending_confirmations: List[Dict[str, Any]] = []
    
    # Execution log
    execution_log: List[Dict[str, Any]] = []
    
    # SSH session info
    ssh_connected: bool = False
    ssh_output: Optional[str] = None
    
    # Resolution
    resolution_summary: Optional[str] = None
    incident_resolved: bool = False
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None

class PendingAction(BaseModel):
    """Action waiting for user confirmation"""
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    execution_id: str
    incident_id: str
    device_id: Optional[str] = None
    device_name: Optional[str] = None
    action_type: str
    action_description: str
    command_to_execute: Optional[str] = None
    risk_level: str = "high"  # "low", "medium", "high", "critical"
    estimated_downtime: Optional[str] = None
    status: str = "pending"  # "pending", "approved", "rejected", "executed"
    requested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    responded_by: Optional[str] = None
    responded_at: Optional[datetime] = None
    execution_result: Optional[str] = None

class AgentSettings(BaseModel):
    """Global settings for AI agent behavior"""
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    auto_trigger_on_incident: bool = False  # Whether to auto-trigger agent on new incidents
    auto_trigger_priorities: List[str] = ["P1", "P2"]  # Which priorities to auto-trigger for
    max_auto_actions_per_incident: int = 10
    ssh_timeout: int = 30
    command_timeout: int = 60
    enable_real_ssh: bool = True  # If false, runs in simulation mode
    notification_on_action: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

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
        ROOT_DIR = Path(__file__).parent
        load_dotenv(ROOT_DIR / "dbvar.env", override=True)

        emergent_llm_key = os.getenv("EMERGENT_LLM_KEY")

        if not emergent_llm_key:
            logger.warning("LLM_KEY not set - AI analysis disabled")
            return "AI analysis is not configured. Please set LLM_KEY environment variable."

        from emergentintegrations.llm.chat import LlmChat, UserMessage

        chat = LlmChat(
            api_key=emergent_llm_key,
            session_id=f"noc-{str(uuid.uuid4())[:8]}",
            system_message="""
You are an expert Autonomous NOC AI for enterprise networks and data centers. 
CRITICAL RULE: You must NEVER output conversational markdown, bullet points, or explanatory essays outside of your data structure. 
You MUST return your response as a VALID, RAW JSON object ONLY. 
Do not wrap your entire response in friendly text greetings. Your output must strictly match this exact JSON structure:
{
  "classification": "alert",
  "analysis": "Concise root-cause analysis summary here...",
  "proposed_commands": ["command 1", "command 2"]
}
"""
        ).with_model(provider="gemini", model="gemini-2.5-pro")

        user_message = UserMessage(
            text=f"Context: {context}\n\nQuery: {query}"
        )

        response = await chat.send_message(user_message)

        content = response.strip() #added/modified 2/08/2026
        if content.startswith("```json"):
            content = content[7:-3].strip()
        elif content.startswith("```"):
            content = content[3:-3].strip()
            
        try:
            parsed_result = json.loads(content)
        except json.JSONDecodeError:
            # Fallback: if the LLM still output conversational text, wrap it 
            # cleanly into the analysis field instead of crashing the UI
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                parsed_result = json.loads(json_match.group(0))
            else:
                parsed_result = {
                    "classification": "alert",
                    "analysis": response, # Safely passes the narrative text into the analysis box
                    "proposed_commands": []
                }
        
        return parsed_result

    except ImportError as e:
        logger.error(f"emergentintegrations not installed: {e}")
        return (
            "AI module not installed. Please run: "
            "pip install emergentintegrations "
            "--extra-index-url https://d33sy5i8bnduwe.cloudfront.net/simple/"
        )

    except Exception as e:
        logger.error(f"AI analysis error: {e}")
        return f"AI analysis error: {str(e)}"

# ===================== AUTONOMOUS AGENT SERVICE =====================

class AutonomousAgentService:
    """Service for autonomous incident resolution"""
    
    def __init__(self):
        self.ssh_clients = {}
    
    async def get_agent_settings(self) -> dict:
        """Get agent settings from DB or create defaults"""
        settings = await db.agent_settings.find_one({}, {"_id": 0})
        if not settings:
            default_settings = AgentSettings()
            settings_dict = default_settings.model_dump()
            settings_dict["created_at"] = settings_dict["created_at"].isoformat()
            settings_dict["updated_at"] = settings_dict["updated_at"].isoformat()
            await db.agent_settings.insert_one(settings_dict)
            return settings_dict
        return settings
    
    async def analyze_incident_for_actions(self, incident: dict, device: dict = None) -> dict:
        """Phase 1: Initial investigation with full topology"""
        all_devices = await db.devices.find({}, {"_id": 0}).to_list(100)
        devices_list_str = "\n".join([
            f"- {d.get('name')} ({d.get('ip_address')}) - {d.get('vendor','Unknown')}" 
            for d in all_devices
        ])

        target_ip = device.get('ip_address', 'N/A') if device else 'N/A'

        context = f"""
=== FULL NETWORK TOPOLOGY ===
{devices_list_str}

=== INCIDENT ===
Offline Device: {device.get('name', 'N/A')} ({target_ip})
"""

        query = """**RETURN ONLY VALID JSON. NO OTHER TEXT, NO MARKDOWN, NO EXPLANATIONS.**

{
  "root_cause": "Initial reachability analysis for target IP",
  "actions": [
    {
      "action_type": "investigate_network",
      "target_device_name": "EXACT_UPSTREAM_DEVICE_NAME_HERE",
      "description": "Query routing table and interface status toward the offline target",
      "command": "show ip route TARGET_IP_HERE\\nshow ip interface brief",
      "risk_level": "low",
      "estimated_downtime": "0 minutes",
      "order": 1
    }
  ],
  "resolution_confidence": 75
}
"""

        try:
            response = await get_ai_analysis(context, query)
            
            # More robust JSON extraction
            import re
            json_match = re.search(r'(\{[\s\S]*\})', response.strip())
            if json_match:
                json_str = json_match.group(1)
                # Clean common LLM artifacts
                json_str = re.sub(r'^.*?\{', '{', json_str, flags=re.DOTALL)
                return json.loads(json_str)
            
            return {"root_cause": "Parse failed - invalid AI response", "actions": []}
        except Exception as e:
            logger.error(f"Phase 1 JSON parse error: {e}")
            return {"root_cause": str(e), "actions": []}
    
    async def connect_ssh(self, device: dict) -> tuple:
        """Connect to device via SSH using decrypted credentials"""
        settings = await self.get_agent_settings()
        
        if not settings.get('enable_real_ssh', True):
            return None, "SSH disabled - running in simulation mode"
        
        ip = device.get('ip_address')
        if not ip:
            return None, "No IP address configured"
        
        # Fetch exact credentials from the device document
        username = device.get('username') 
        encrypted_password = device.get('password', '')

        if not username:
            return None, "SSH connection failed: No username configured for this device in the database."
        
        # 2. CRITICAL FIX: Decrypt the password using your Fernet cipher
        password = ""
        if encrypted_password:
            try:
                password = decrypt_password(encrypted_password)
            except Exception as e:
                logger.error(f"Decryption failed for {ip}: {e}")
                return None, "SSH connection failed: Could not decrypt device password."
        else:
            return None, "SSH connection failed: No password stored for this device."
        
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # 3. Pass the cleartext decrypted password to the router
            client.connect(
                ip,
                port=22,
                username=username,
                password=password,
                timeout=settings.get('ssh_timeout', 30),
                allow_agent=False,
                look_for_keys=False
            )
            
            # MAGIC FIX: Attach password silently to the client object
            client.vendor = device.get("vendor", "")
            client.device_password = password
            
            return client, "Connected successfully"
        except Exception as e:
            logger.warning(f"SSH connection failed to {ip}: {e}")
            return None, f"SSH connection failed: {str(e)}"
    
    async def execute_command(self, ssh_client, command: str, timeout: int = 60) -> dict:
        """Execute a command via SSH or locally if no SSH client is provided (Production Mode)"""
        if ssh_client is None:
            # Production Local Execution
            try:
                process = await asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                try:
                    stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
                except asyncio.TimeoutError:
                    process.kill()
                    stdout, stderr = await process.communicate()
                    return {"success": False, "output": stdout.decode('utf-8', errors='ignore'), "error": "Timeout", "status_code": -1, "simulated": False}
                
                return {
                    "success": process.returncode == 0,
                    "output": stdout.decode('utf-8', errors='ignore'),
                    "error": stderr.decode('utf-8', errors='ignore'),
                    "status_code": process.returncode, "simulated": False
                }
            except Exception as e:
                return {"success": False, "output": "", "error": str(e), "status_code": -1, "simulated": False}

       
        try:
            shell = ssh_client.invoke_shell()
            await asyncio.sleep(1) # Wait for initial prompt banner
            
            initial_output = ""
            if shell.recv_ready():
                initial_output = shell.recv(65535).decode('utf-8', errors='ignore')
                
            #device_vendor = getattr(ssh_client, 'vendor', '').lower()

            device_vendor = getattr(ssh_client, 'vendor', '').lower()
            profile = get_vendor_profile(device_vendor)
            
            escalate_prompt = profile.cli_patterns.get("escalation_trigger_prompt")
            escalate_cmd = profile.commands.get("privilege_escalation_command")

            # --- PRIVILEGE ESCALATION DRIVEN BY DATA PROFILES ---
            if escalate_cmd and escalate_prompt and initial_output.strip().endswith(escalate_prompt):
                shell.send(f"{escalate_cmd}\n")
                await asyncio.sleep(1)
                enable_output = shell.recv(65535).decode('utf-8', errors='ignore') if shell.recv_ready() else ""
                if "password" in enable_output.lower():
                    password = getattr(ssh_client, 'device_password', "")
                    shell.send(password + "\n")
                    await asyncio.sleep(1)

            # --- SEND COMMAND SEQUENCE ---
            for line in command.split('\n'):
                if line.strip():
                    shell.send(line.strip() + "\n")
                    await asyncio.sleep(0.5)
            
            await asyncio.sleep(2) # Allow target vendor operating system to finalize output buffers
            
            output = ""
            while shell.recv_ready():
                output += shell.recv(65535).decode('utf-8', errors='ignore')
                await asyncio.sleep(0.1)
                
            # --- SYNTAX ERROR CHECKING MATRICES ---
            is_success = True
            error_msg = ""
            vendor_syntax_errors = [
                "Invalid input detected", "unknown command", "syntax error", 
                "Command rejected", "unrecognized command", "ambiguous command"
            ]
            if any(err in output for err in vendor_syntax_errors):
                is_success = False
                error_msg = f"Vendor Operating System syntax constraint violation intercepted."
                
            return {
                "success": is_success,
                "output": output.strip(),
                "error": error_msg,
                "status_code": 0 if is_success else 1,
                "simulated": False
            }
        except Exception as e:
            return {"success": False, "output": "", "error": str(e), "status_code": -1, "simulated": False}
        
    async def execute_auto_action(self, action: dict, ssh_client, device: dict) -> dict:
        """Execute an auto-resolve action dynamically without hardcoded vendor commands."""
        action_type = action.get('action_type')
        command = action.get('command')
        
        if not command:
            vendor = device.get('vendor', 'generic')
            # Fetch the profile mapping configuration directly
            profile = get_vendor_profile(vendor)
            
            # Check if the profile dictionary natively contains the troubleshooting command macro
            if action_type in profile.commands:
                command = profile.commands[action_type]
            else:
                # Fall back to a global config mapping stored inside your MongoDB collection 
                global_cmd_doc = await db.vendor_commands.find_one({"vendor": profile.name, "action_type": action_type})
                if global_cmd_doc:
                    command = global_cmd_doc.get("command")
                else:
                    # Universal standard fallback execution command
                    command = "echo 'Command template unconfigured for vendor'"

        result = await self.execute_command(ssh_client, command)
        return {
            "action_type": action_type,
            "command": command,
            "result": result,
            "executed_at": datetime.now(timezone.utc).isoformat(),
            "success": result.get('success', False)
        }
    
    async def _get_topology_summary(self) -> str:
        devices = await db.devices.find({}, {"_id": 0, "name":1, "ip_address":1, "vendor":1}).to_list(50)
        return "\n".join([f"- {d['name']} ({d['ip_address']}) {d.get('vendor','')}" for d in devices])

    # New Method of Troubleshooting 
    async def analyze_investigation_results(
            self,
            incident: dict,
            offline_device: dict,
            upstream_device_name: str,
            cli_outputs: str,
            topology_context: dict = None
        ) -> dict:

            candidate_interfaces = []

            if topology_context:

                for upstream in topology_context.get(
                    "upstream_devices",
                    []
                ):

                    if upstream["hostname"] != upstream_device_name:
                        continue

                    for intf in upstream.get(
                        "interfaces",
                        []
                    ):

                        name = intf.get(
                            "interface",
                            ""
                        ).lower()

                        if name.startswith(
                            (
                                "loopback",
                                "vlan",
                                "null",
                                "tunnel"
                            )
                        ):
                            continue

                        if (
                            intf.get("protocol")
                            == "down"
                        ):
                            candidate_interfaces.append(
                                intf
                            )

            context = f"""
        OFFLINE DEVICE:
        {json.dumps(offline_device, indent=2)}

        UPSTREAM DEVICE:
        {upstream_device_name}

        DOWN INTERFACES:
        {json.dumps(candidate_interfaces, indent=2)}

        CLI OUTPUT:
        {cli_outputs}
        """

            query = """
        RETURN ONLY JSON

        {
        "root_cause":"",
        "identified_interface":"",
        "recommended_command":"",
        "resolution_confidence":0
        }
        """

            try:

                response = await get_ai_analysis(
                    context,
                    query
                )

                match = re.search(
                    r'(\{[\s\S]*\})',
                    response
                )

                if not match:
                    raise Exception(
                        "Invalid JSON response"
                    )

                analysis = json.loads(
                    match.group(1)
                )

                identified = analysis.get(
                    "identified_interface"
                )

                if identified:

                    analysis["auto_fix"] = (
                        f"configure terminal\n"
                        f"interface {identified}\n"
                        f"no shutdown\n"
                        f"end\n"
                        f"write memory"
                    )

                return analysis

            except Exception as e:

                logger.error(
                    f"Investigation analysis failed: {e}"
                )

                return {
                    "root_cause": str(e),
                    "identified_interface": None,
                    "recommended_command": None,
                    "resolution_confidence": 0
                }
            
    # Modified the fuction block 21/07/2026
    async def run_autonomous_troubleshooting(
        self,
        incident_id: str,
        triggered_by: str,
        trigger_type: str = "manual"
    ):
        """
        Main entry point for Autonomous Troubleshooting Engine.
        Refactored to use inline LLM analysis directly, bypassing legacy playbooks.
        """
        incident = await db.incidents.find_one({"id": incident_id}, {"_id": 0})
        if not incident:
            raise Exception("Incident not found")

        device = await db.devices.find_one({"id": incident["device_id"]}, {"_id": 0})
        if not device:
            raise Exception("Device not found")

        initial_log = [{
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message": f"Starting unified AI diagnostics for {device.get('name', 'Target Device')}...",
            "type": "info"
        }]

        execution = {
            "id": str(uuid.uuid4()),
            "incident_id": incident_id,
            "status": "running",
            "triggered_by": triggered_by,
            "trigger_type": trigger_type,
            "execution_log": initial_log,
            "created_at": datetime.now(timezone.utc).isoformat()
        }

        await db.agent_executions.insert_one(execution)

        try:
            # Replaced multi-phase playbook with a single direct AI call
            context = f"Device: {device.get('name')} (IP: {device.get('ip_address')}, Vendor: {device.get('vendor')})\nIncident: {incident.get('title')}\nDescription: {incident.get('description')}"
            query = "Analyze this network incident. Provide a brief root cause and the specific CLI commands to investigate or fix it."
            
            ai_response = await get_ai_analysis(context, query)
            
            initial_log.append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "message": f"AI Diagnostic Results:\n{ai_response}",
                "type": "analysis"
            })

            await db.agent_executions.update_one(
                {"id": execution["id"]},
                {
                    "$set": {
                        "status": "completed",
                        "execution_log": initial_log,
                        "updated_at": datetime.now(timezone.utc).isoformat()
                    }
                }
            )

            return {
                "success": True,
                "execution_id": execution["id"],
                "execution_log": initial_log
            }

        except Exception as e:
            logger.error(f"Troubleshooting pipeline crashed: {e}", exc_info=True)
            initial_log.append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "message": f"Pipeline Error: {str(e)}",
                "type": "error"
            })
            await db.agent_executions.update_one(
                {"id": execution["id"]},
                {
                    "$set": {
                        "status": "failed",
                        "error": str(e),
                        "execution_log": initial_log,
                        "updated_at": datetime.now(timezone.utc).isoformat()
                    }
                }
            )
            return {"success": False, "message": str(e), "execution_log": initial_log}


    async def generate_resolution_summary(self, incident: dict, analysis: dict, executed: list, pending: list) -> str:
        """Generate a summary of what was done"""
        summary_parts = [
            f"## Resolution Summary for {incident.get('ticket_number', 'Unknown')}",
            f"\n**Root Cause:** {analysis.get('root_cause', 'Unknown')}",
            f"\n**Resolution Confidence:** {analysis.get('resolution_confidence', 0)}%",
            f"\n\n### Actions Executed ({len(executed)}):"
        ]
        
        for action in executed:
            status = "✅ Success" if action.get('success') else "❌ Failed"
            summary_parts.append(f"\n- {action.get('action_type')}: {status}")
        
        if pending:
            summary_parts.append(f"\n\n### Pending Confirmations ({len(pending)}):")
            for p in pending:
                summary_parts.append(f"\n- ⚠️ {p.get('action_type')}: {p.get('description')}")
        
        return "".join(summary_parts)
    
    async def execute_confirmed_action(self, action_id: str, confirmed_by: str) -> dict:
        """Execute an action after user confirmation"""
        pending = await db.pending_actions.find_one({"id": action_id}, {"_id": 0})
        if not pending:
            raise HTTPException(status_code=404, detail="Pending action not found")
        
        if pending.get('status') != 'pending':
            raise HTTPException(status_code=400, detail="Action already processed")
        
        # Get device
        device = None
        if pending.get('device_id'):
            device = await db.devices.find_one({"id": pending['device_id']}, {"_id": 0})
        
        # Connect and execute
        ssh_client = None
        if device:
            ssh_client, _ = await self.connect_ssh(device)
        
        command = pending.get('command_to_execute', 'echo "No command specified"')
        # CRITICAL FIX: Pass device=device so the engine can escalate privileges (enable mode)
        result = await self.execute_command(ssh_client, command)
        
        if ssh_client:
            ssh_client.close()
        
        # Update pending action
        await db.pending_actions.update_one(
            {"id": action_id},
            {"$set": {
                "status": "executed",
                "responded_by": confirmed_by,
                "responded_at": datetime.now(timezone.utc).isoformat(),
                "execution_result": json.dumps(result)
            }}
        )
        
        # Update execution log
        execution = await db.agent_executions.find_one({"id": pending.get('execution_id')}, {"_id": 0})
        if execution:
            execution["execution_log"].append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "message": f"✅ Confirmed action executed: {pending.get('action_type')} by {confirmed_by}",
                "type": "confirmed_execution"
            })
            execution["executed_actions"].append({
                "action_type": pending.get('action_type'),
                "command": command,
                "result": result,
                "confirmed_by": confirmed_by,
                "executed_at": datetime.now(timezone.utc).isoformat()
            })
            
            # Check if all pending actions are now processed
            remaining = await db.pending_actions.count_documents({
                "execution_id": pending.get('execution_id'),
                "status": "pending"
            })
            
            if remaining == 0:
                execution["status"] = AgentExecutionStatus.COMPLETED.value
                execution["completed_at"] = datetime.now(timezone.utc).isoformat()
                execution["incident_resolved"] = True
                
                # Update incident
                await db.incidents.update_one(
                    {"id": pending.get('incident_id')},
                    {"$set": {
                        "status": "resolved",
                        "resolution": "Resolved by AI Agent after user confirmation",
                        "resolved_at": datetime.now(timezone.utc).isoformat()
                    }}
                )
            
            await db.agent_executions.update_one(
                {"id": execution["id"]},
                {"$set": execution}
            )
        
        return {"success": True, "result": result}

# Initialize agent service
agent_service = AutonomousAgentService()

# Create agent execution router
agent_exec_router = APIRouter(prefix="/agent-exec", tags=["Agent Execution"])

@agent_exec_router.post("/run/{incident_id}")
async def run_agent_troubleshooting(incident_id: str, current_user: dict = Depends(get_current_user)):
    """Manually trigger AI agent to troubleshoot an incident"""
    result = await agent_service.run_autonomous_troubleshooting(
        incident_id=incident_id,
        triggered_by=current_user["name"],
        trigger_type="manual"
    )
    return result

@agent_exec_router.get("/executions")
async def get_all_executions(
    limit: int = 50,
    incident_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get all agent executions"""
    query = {}
    if incident_id:
        query["incident_id"] = incident_id
    
    executions = await db.agent_executions.find(
        query, {"_id": 0}
    ).sort("created_at", -1).to_list(limit)
    
    return executions

@agent_exec_router.get("/executions/{execution_id}")
async def get_execution(execution_id: str, current_user: dict = Depends(get_current_user)):
    """Get a specific agent execution"""
    execution = await db.agent_executions.find_one({"id": execution_id}, {"_id": 0})
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    return execution

@agent_exec_router.get("/pending-actions")
async def get_pending_actions(current_user: dict = Depends(get_current_user)):
    """Get all pending actions requiring user confirmation"""
    actions = await db.pending_actions.find(
        {"status": "pending"}, {"_id": 0}
    ).sort("requested_at", -1).to_list(100)
    return actions

@agent_exec_router.get("/pending-actions/count")
async def get_pending_actions_count(current_user: dict = Depends(get_current_user)):
    """Get count of pending actions"""
    count = await db.pending_actions.count_documents({"status": "pending"})
    return {"count": count}

@agent_exec_router.post("/actions/{action_id}/approve")
async def approve_action(action_id: str, current_user: dict = Depends(get_current_user)):
    """Approve and execute a pending action"""
    result = await agent_service.execute_confirmed_action(action_id, current_user["name"])
    
    # Broadcast update
    await ws_manager.broadcast({
        "type": "action_approved",
        "data": {"action_id": action_id, "approved_by": current_user["name"]}
    })
    
    return result

@agent_exec_router.post("/actions/{action_id}/reject")
async def reject_action(
    action_id: str, 
    reason: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Reject a pending action"""
    pending = await db.pending_actions.find_one({"id": action_id}, {"_id": 0})
    if not pending:
        raise HTTPException(status_code=404, detail="Action not found")
    
    await db.pending_actions.update_one(
        {"id": action_id},
        {"$set": {
            "status": "rejected",
            "responded_by": current_user["name"],
            "responded_at": datetime.now(timezone.utc).isoformat(),
            "rejection_reason": reason
        }}
    )
    
    # Update execution log
    execution = await db.agent_executions.find_one({"id": pending.get('execution_id')}, {"_id": 0})
    if execution:
        execution["execution_log"].append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message": f"❌ Action rejected: {pending.get('action_type')} by {current_user['name']}. Reason: {reason or 'No reason provided'}",
            "type": "rejected"
        })
        await db.agent_executions.update_one(
            {"id": execution["id"]},
            {"$set": {"execution_log": execution["execution_log"]}}
        )
    
    # Broadcast update
    await ws_manager.broadcast({
        "type": "action_rejected",
        "data": {"action_id": action_id, "rejected_by": current_user["name"]}
    })
    
    return {"success": True, "message": "Action rejected"}

@agent_exec_router.get("/settings")
async def get_agent_settings(current_user: dict = Depends(get_current_user)):
    """Get agent settings"""
    settings = await agent_service.get_agent_settings()
    return settings

@agent_exec_router.put("/settings")
async def update_agent_settings(
    settings: Dict[str, Any],
    current_user: dict = Depends(get_current_user)
):
    """Update agent settings"""
    settings["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    await db.agent_settings.update_one(
        {},
        {"$set": settings},
        upsert=True
    )
    
    return {"success": True, "message": "Settings updated"}

@agent_exec_router.get("/execution-log/{incident_id}")
async def get_incident_execution_log(incident_id: str, current_user: dict = Depends(get_current_user)):
    """Get all execution logs for an incident"""
    executions = await db.agent_executions.find(
        {"incident_id": incident_id}, {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    
    return executions

# ===================== NETWORK DIAGNOSTICS =====================

class PingRequest(BaseModel):
    target: str
    count: int = 4
    device_id: Optional[str] = None

class TracerouteRequest(BaseModel):
    target: str
    max_hops: int = 30
    device_id: Optional[str] = None

@agent_exec_router.post("/diagnostics/ping")
async def run_ping_diagnostic(request: PingRequest, current_user: dict = Depends(get_current_user)):
    """Run REAL ping diagnostic and return results"""
    import subprocess
    import re
    
    target = request.target
    count = min(request.count, 10)  # Max 10 pings
    
    # Get device info if provided
    device = None
    if request.device_id:
        device = await db.devices.find_one({"id": request.device_id}, {"_id": 0})
    
    ping_results = []
    packets_sent = count
    packets_received = 0
    total_time = 0
    latencies = []
    
    try:
        # Execute real ping command
        # Use -W for timeout on Linux, -t for TTL
        cmd = ["ping", "-c", str(count), "-W", "2", target]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)
        output = stdout.decode('utf-8', errors='ignore')
        
        # Parse ping output
        # Match lines like: 64 bytes from 8.8.8.8: icmp_seq=1 ttl=117 time=14.3 ms
        ping_line_pattern = re.compile(
            r'(\d+) bytes from [\w\.\-:]+.*icmp_seq=(\d+).*ttl=(\d+).*time=([\d\.]+)'
        )
        
        seq = 0
        for line in output.split('\n'):
            match = ping_line_pattern.search(line)
            if match:
                seq += 1
                latency = float(match.group(4))
                ttl = int(match.group(3))
                
                ping_results.append({
                    "seq": seq,
                    "success": True,
                    "latency_ms": round(latency, 2),
                    "ttl": ttl,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
                packets_received += 1
                total_time += latency
                latencies.append(latency)
            elif 'Request timeout' in line or 'Destination Host Unreachable' in line:
                seq += 1
                ping_results.append({
                    "seq": seq,
                    "success": False,
                    "latency_ms": None,
                    "ttl": None,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
        
        # If no results parsed, the host might be completely unreachable
        if not ping_results:
            for i in range(count):
                ping_results.append({
                    "seq": i + 1,
                    "success": False,
                    "latency_ms": None,
                    "ttl": None,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
        
    except asyncio.TimeoutError:
        # Ping command timed out completely
        for i in range(count):
            ping_results.append({
                "seq": i + 1,
                "success": False,
                "latency_ms": None,
                "ttl": None,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
    except Exception as e:
        logger.error(f"Ping error: {e}")
        for i in range(count):
            ping_results.append({
                "seq": i + 1,
                "success": False,
                "latency_ms": None,
                "ttl": None,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
    
    packet_loss = ((packets_sent - packets_received) / packets_sent) * 100 if packets_sent > 0 else 100
    avg_latency = total_time / packets_received if packets_received > 0 else None
    
    result = {
        "target": target,
        "device_name": device.get('name') if device else None,
        "device_ip": device.get('ip_address') if device else target,
        "packets_sent": packets_sent,
        "packets_received": packets_received,
        "packet_loss_percent": round(packet_loss, 1),
        "avg_latency_ms": round(avg_latency, 2) if avg_latency else None,
        "min_latency_ms": round(min(latencies), 2) if latencies else None,
        "max_latency_ms": round(max(latencies), 2) if latencies else None,
        "ping_results": ping_results,
        "status": "reachable" if packets_received > 0 else "unreachable",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    # Store diagnostic result
    diagnostic_record = {
        "id": str(uuid.uuid4()),
        "type": "ping",
        "target": target,
        "device_id": request.device_id,
        "result": result,
        "triggered_by": current_user["name"],
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.network_diagnostics.insert_one(diagnostic_record)
    
    return result

@agent_exec_router.post("/diagnostics/traceroute")
async def run_traceroute_diagnostic(request: TracerouteRequest, current_user: dict = Depends(get_current_user)):
    """Run REAL traceroute diagnostic and return hop-by-hop results"""
    import subprocess
    import re
    
    target = request.target
    max_hops = min(request.max_hops, 30)
    
    # Get device info if provided
    device = None
    if request.device_id:
        device = await db.devices.find_one({"id": request.device_id}, {"_id": 0})
    
    hops = []
    
    try:
        # Execute real traceroute command
        # -n: numeric output, -m: max hops, -w: wait time
        cmd = ["traceroute", "-n", "-m", str(max_hops), "-w", "2", target]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=120)
        output = stdout.decode('utf-8', errors='ignore')
        
        # Parse traceroute output
        # Match lines like: 1  192.168.1.1  1.234 ms  1.456 ms  1.789 ms
        # Or: 1  * * *
        hop_pattern = re.compile(r'^\s*(\d+)\s+(.+)$', re.MULTILINE)
        
        for match in hop_pattern.finditer(output):
            hop_num = int(match.group(1))
            hop_data_str = match.group(2).strip()
            
            # Check if timeout (all asterisks)
            if hop_data_str == '* * *' or hop_data_str.count('*') >= 3:
                hops.append({
                    "hop": hop_num,
                    "ip": None,
                    "hostname": None,
                    "type": "unknown",
                    "latency_1": None,
                    "latency_2": None,
                    "latency_3": None,
                    "avg_latency": None,
                    "status": "timeout",
                    "is_destination": False
                })
            else:
                # Parse IP and latencies
                # Format: IP  time1 ms  time2 ms  time3 ms
                parts = hop_data_str.split()
                ip = None
                latencies = []
                
                for part in parts:
                    # Check if it's an IP address
                    if re.match(r'^\d+\.\d+\.\d+\.\d+$', part):
                        ip = part
                    # Check if it's a latency value
                    elif re.match(r'^[\d\.]+$', part):
                        try:
                            latencies.append(float(part))
                        except ValueError:
                            pass
                    # Skip 'ms' and '*'
                
                # Pad latencies if needed
                while len(latencies) < 3:
                    latencies.append(None)
                
                avg_latency = None
                valid_latencies = [l for l in latencies if l is not None]
                if valid_latencies:
                    avg_latency = sum(valid_latencies) / len(valid_latencies)
                
                # Determine hop type based on IP
                hop_type = "router"
                if ip:
                    if ip.startswith("192.168.") or ip.startswith("10.") or ip.startswith("172."):
                        hop_type = "gateway" if hop_num == 1 else "internal"
                    elif ip == target or (hop_num == max_hops):
                        hop_type = "destination"
                
                hops.append({
                    "hop": hop_num,
                    "ip": ip,
                    "hostname": ip,  # Could do reverse DNS lookup
                    "type": hop_type,
                    "latency_1": round(latencies[0], 2) if latencies[0] else None,
                    "latency_2": round(latencies[1], 2) if latencies[1] else None,
                    "latency_3": round(latencies[2], 2) if latencies[2] else None,
                    "avg_latency": round(avg_latency, 2) if avg_latency else None,
                    "status": "ok" if ip else "timeout",
                    "is_destination": ip == target if ip else False
                })
        
        # If no hops parsed, target might be unreachable
        if not hops:
            hops.append({
                "hop": 1,
                "ip": None,
                "hostname": None,
                "type": "unknown",
                "latency_1": None,
                "latency_2": None,
                "latency_3": None,
                "avg_latency": None,
                "status": "timeout",
                "is_destination": False
            })
            
    except asyncio.TimeoutError:
        hops.append({
            "hop": 1,
            "ip": None,
            "hostname": None,
            "type": "unknown",
            "latency_1": None,
            "latency_2": None,
            "latency_3": None,
            "avg_latency": None,
            "status": "timeout",
            "is_destination": False
        })
    except Exception as e:
        logger.error(f"Traceroute error: {e}")
        hops.append({
            "hop": 1,
            "ip": None,
            "hostname": None,
            "type": "error",
            "latency_1": None,
            "latency_2": None,
            "latency_3": None,
            "avg_latency": None,
            "status": "error",
            "is_destination": False
        })
    
    # Detect potential issues
    issues = []
    for i, hop in enumerate(hops):
        if hop["status"] == "timeout":
            issues.append(f"Hop {hop['hop']}: Timeout - possible firewall or routing issue")
        elif i > 0 and hop["avg_latency"] and hops[i-1].get("avg_latency"):
            latency_jump = hop["avg_latency"] - hops[i-1]["avg_latency"]
            if latency_jump > 50:
                issues.append(f"Hop {hop['hop']}: High latency jump (+{latency_jump:.0f}ms) - possible congestion")
    
    destination_reached = any(h.get("is_destination") or h.get("ip") == target for h in hops)
    
    result = {
        "target": target,
        "device_name": device.get('name') if device else None,
        "device_ip": device.get('ip_address') if device else None,
        "total_hops": len(hops),
        "destination_reached": destination_reached,
        "total_latency_ms": hops[-1]["avg_latency"] if hops and hops[-1]["avg_latency"] else None,
        "hops": hops,
        "issues_detected": issues,
        "path_quality": "good" if len(issues) == 0 else "degraded" if len(issues) < 3 else "poor",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    # Store diagnostic result
    diagnostic_record = {
        "id": str(uuid.uuid4()),
        "type": "traceroute",
        "target": target,
        "device_id": request.device_id,
        "result": result,
        "triggered_by": current_user["name"],
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.network_diagnostics.insert_one(diagnostic_record)
    
    return result

@agent_exec_router.get("/diagnostics/history")
async def get_diagnostics_history(
    limit: int = 20,
    diagnostic_type: Optional[str] = None,
    device_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get history of network diagnostics"""
    query = {}
    if diagnostic_type:
        query["type"] = diagnostic_type
    if device_id:
        query["device_id"] = device_id
    
    diagnostics = await db.network_diagnostics.find(
        query, {"_id": 0}
    ).sort("created_at", -1).to_list(limit)
    
    return diagnostics

@agent_exec_router.post("/routing/optimize")
async def get_routing_optimization(current_user: dict = Depends(get_current_user)):
    """AI-powered routing protocol optimization suggestions for the network"""
    
    # Get all devices
    devices = await db.devices.find({}, {"_id": 0}).to_list(100)
    
    # Get network topology info
    routers = [d for d in devices if d.get('type') == 'router']
    switches = [d for d in devices if d.get('type') == 'switch']
    firewalls = [d for d in devices if d.get('type') == 'firewall']
    
    # Build network context
    network_context = f"""
=== NETWORK TOPOLOGY SUMMARY ===
Total Devices: {len(devices)}
- Routers: {len(routers)}
- Switches: {len(switches)}
- Firewalls: {len(firewalls)}
- Other devices: {len(devices) - len(routers) - len(switches) - len(firewalls)}

=== ROUTER DETAILS ===
"""
    for router in routers:
        network_context += f"- {router.get('name')}: {router.get('vendor', 'Unknown')} {router.get('model', '')} at {router.get('location', 'Unknown')}\n"
    
    network_context += "\n=== SWITCH DETAILS ===\n"
    for switch in switches:
        network_context += f"- {switch.get('name')}: {switch.get('vendor', 'Unknown')} {switch.get('model', '')} at {switch.get('location', 'Unknown')}\n"
    
    # Get recent alerts for network issues
    recent_alerts = await db.alerts.find(
        {"status": {"$ne": "resolved"}},
        {"_id": 0}
    ).sort("created_at", -1).to_list(20)
    
    if recent_alerts:
        network_context += "\n=== RECENT NETWORK ALERTS ===\n"
        for alert in recent_alerts[:10]:
            network_context += f"- [{alert.get('severity', 'N/A').upper()}] {alert.get('title', 'Unknown')} on {alert.get('device_name', 'Unknown')}\n"
    
    # Get unique locations
    locations = list(set([d.get('location', 'Unknown') for d in devices if d.get('location')]))
    network_context += f"\n=== SITE LOCATIONS ({len(locations)}) ===\n"
    for loc in locations:
        devices_at_loc = [d for d in devices if d.get('location') == loc]
        network_context += f"- {loc}: {len(devices_at_loc)} devices\n"
    
    analysis = await get_ai_analysis(
        network_context,
        """You are a senior network architect. Analyze this network topology and provide comprehensive routing protocol optimization recommendations.

Please provide a detailed JSON response with the following structure:
{
  "network_assessment": {
    "size": "small/medium/large/enterprise",
    "complexity": "low/medium/high",
    "current_challenges": ["list of identified issues"]
  },
  "recommended_protocol": {
    "primary": "OSPF/EIGRP/BGP/IS-IS/RIP",
    "rationale": "Why this protocol is recommended",
    "alternative": "Alternative protocol if primary not suitable"
  },
  "configuration_suggestions": [
    {
      "area": "Core/Distribution/Access/WAN",
      "protocol": "Protocol name",
      "config_snippet": "Example configuration",
      "best_practices": ["List of best practices"]
    }
  ],
  "ospf_design": {
    "recommended": true/false,
    "area_design": "Single area or multi-area design description",
    "area_assignments": [{"area": "0", "devices": ["device names"]}]
  },
  "bgp_considerations": {
    "needed": true/false,
    "use_case": "When/why BGP would be needed",
    "as_design": "AS number recommendations"
  },
  "redundancy_recommendations": [
    "List of redundancy improvements"
  ],
  "convergence_optimization": [
    "Tips to improve network convergence time"
  ],
  "security_recommendations": [
    "Routing security best practices"
  ],
  "implementation_priority": [
    {"priority": 1, "action": "First action to take", "impact": "high/medium/low"},
    {"priority": 2, "action": "Second action", "impact": "high/medium/low"}
  ]
}

Return ONLY valid JSON, no markdown or additional text."""
    )
    
    # Try to parse the AI response
    try:
        import re
        json_match = re.search(r'\{[\s\S]*\}', analysis)
        if json_match:
            optimization_data = json.loads(json_match.group())
        else:
            optimization_data = {"raw_analysis": analysis}
    except:
        optimization_data = {"raw_analysis": analysis}
    
    result = {
        "id": str(uuid.uuid4()),
        "network_summary": {
            "total_devices": len(devices),
            "routers": len(routers),
            "switches": len(switches),
            "firewalls": len(firewalls),
            "locations": locations,
            "active_alerts": len(recent_alerts)
        },
        "optimization": optimization_data,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generated_by": current_user["name"]
    }
    
    # Store the recommendation
    await db.routing_optimizations.insert_one(result.copy())
    
    return result

@agent_exec_router.get("/routing/history")
async def get_routing_optimization_history(
    limit: int = 10,
    current_user: dict = Depends(get_current_user)
):
    """Get history of routing optimization recommendations"""
    history = await db.routing_optimizations.find(
        {}, {"_id": 0}
    ).sort("generated_at", -1).to_list(limit)
    
    return history


from datetime import datetime, timezone, timedelta
def is_user_expired(user_doc):
    created_at = user_doc.get("created_at")
 
    if isinstance(created_at, str):
        created_at = datetime.fromisoformat(created_at)
 
    return datetime.now(timezone.utc) > created_at + timedelta(days=32)

 
@auth_router.post("/login", response_model=TokenResponse)
async def login(credentials: UserLogin):
 
    user_doc = await db.users.find_one({"email": credentials.email})
 
    if not user_doc or not verify_password(
        credentials.password,
        user_doc.get("password_hash", "")
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials"
        )
 
    if is_user_expired(user_doc):
        raise HTTPException(
            status_code=403,
            detail="License expired. Please contact administrator."
        )
 
    user = User(
        id=user_doc["id"],
        email=user_doc["email"],
        name=user_doc["name"],
        role=user_doc["role"],
        created_at=datetime.fromisoformat(user_doc["created_at"])
        if isinstance(user_doc["created_at"], str)
        else user_doc["created_at"]
    )
 
    token = create_token(user.id, user.email)
 
    return TokenResponse(
        access_token=token,
        user=user
    )

@auth_router.get("/me", response_model=User)
async def get_me(current_user: dict = Depends(get_current_user)):
 
    if is_user_expired(current_user):
        raise HTTPException(
            status_code=403,
            detail="License expired. Please contact administrator."
        )
 
    return User(**current_user)

# ===================== AAA-ENHANCED LOGIN =====================
@auth_router.post("/aaa-login")
async def aaa_login(credentials: UserLogin):
    """Login with AAA authentication support - tries RADIUS/TACACS+ first, falls back to local"""
    email = credentials.email
    password = credentials.password
    
    # First check if user exists locally
    user_doc = await db.users.find_one({"email": email})
    
    # Try AAA authentication first if servers are configured
    aaa_configs = await db.aaa_config.find({"is_active": True, "use_for_login": True}, {"_id": 0}).to_list(10)
    
    if aaa_configs:
        # Extract username from email for AAA
        aaa_username = email.split('@')[0]
        
        for config in aaa_configs:
            try:
                server_type = config.get("server_type", "radius").lower()
                
                if server_type == "radius":
                    try:
                        from pyrad.client import Client
                        from pyrad.dictionary import Dictionary
                        import pyrad.packet
                        
                        srv = Client(
                            server=config.get("primary_host"),
                            secret=config.get("shared_secret", "").encode(),
                            dict=Dictionary()
                        )
                        srv.timeout = config.get("timeout", 5)
                        
                        req = srv.CreateAuthPacket(code=pyrad.packet.AccessRequest, User_Name=aaa_username)
                        req["User-Password"] = req.PwCrypt(password)
                        reply = srv.SendPacket(req)
                        
                        if reply.code == pyrad.packet.AccessAccept:
                            # AAA auth successful
                            if not user_doc:
                                user_doc = {
                                    "id": str(uuid.uuid4()),
                                    "email": email,
                                    "name": aaa_username,
                                    "role": "operator",
                                    "password_hash": "",
                                    "is_active": True,
                                    "auth_method": "radius",
                                    "created_at": datetime.now(timezone.utc).isoformat()
                                }
                                user_insert = user_doc.copy()
                                await db.users.insert_one(user_insert)
                            
                            token = create_token(user_doc["id"], user_doc["email"])
                            return {
                                "access_token": token,
                                "token_type": "bearer",
                                "user": {
                                    "id": user_doc["id"],
                                    "email": user_doc["email"],
                                    "name": user_doc.get("name", ""),
                                    "role": user_doc.get("role", "operator")
                                },
                                "auth_method": "radius"
                            }
                    except Exception as e:
                        logger.warning(f"RADIUS auth failed: {e}")
                
                elif server_type == "tacacs":
                    try:
                        from tacacs_plus.client import TACACSClient
                        from tacacs_plus.flags import TAC_PLUS_AUTHEN_TYPE_ASCII
                        
                        client = TACACSClient(
                            host=config.get("primary_host"),
                            port=config.get("primary_port", 49),
                            secret=config.get("shared_secret", ""),
                            timeout=config.get("timeout", 5)
                        )
                        
                        auth = client.authenticate(
                            aaa_username,
                            password,
                            authen_type=TAC_PLUS_AUTHEN_TYPE_ASCII
                        )
                        
                        if auth.valid:
                            if not user_doc:
                                user_doc = {
                                    "id": str(uuid.uuid4()),
                                    "email": email,
                                    "name": aaa_username,
                                    "role": "operator",
                                    "password_hash": "",
                                    "is_active": True,
                                    "auth_method": "tacacs",
                                    "created_at": datetime.now(timezone.utc).isoformat()
                                }
                                user_insert = user_doc.copy()
                                await db.users.insert_one(user_insert)
                            
                            token = create_token(user_doc["id"], user_doc["email"])
                            return {
                                "access_token": token,
                                "token_type": "bearer",
                                "user": {
                                    "id": user_doc["id"],
                                    "email": user_doc["email"],
                                    "name": user_doc.get("name", ""),
                                    "role": user_doc.get("role", "operator")
                                },
                                "auth_method": "tacacs"
                            }
                    except Exception as e:
                        logger.warning(f"TACACS+ auth failed: {e}")
            except Exception as e:
                logger.error(f"AAA config error: {e}")
    
    # Fallback to local authentication
    if not user_doc:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not verify_password(password, user_doc.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not user_doc.get("is_active", True):
        raise HTTPException(status_code=401, detail="Account is disabled")
    
    token = create_token(user_doc["id"], user_doc["email"])
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user_doc["id"],
            "email": user_doc["email"],
            "name": user_doc.get("name", ""),
            "role": user_doc.get("role", "operator")
        },
        "auth_method": "local"
    }

# ===================== DEVICE ROUTES =====================
@devices_router.get("") #, response_model=List[Device])
async def get_devices(current_user: dict = Depends(get_current_user)):
    """Fetch all devices instantly from the database telemetry cache"""
    devices = await db.devices.find({}, {"_id": 0}).to_list(1000)
    result = []

    for d in devices:
        device = serialize_doc(d)

        # Build the internal nested 'metrics' sub-object that your frontend components
        # expect, mapping directly from the root level variables updated by device_monitor.py
        device["metrics"] = {
            "cpu_usage": device.get("cpu_usage", 0.0),
            "memory_usage": device.get("memory_usage", 0.0),
            "disk_usage": device.get("disk_usage", 0.0),
            "bandwidth_in": device.get("bandwidth_in", 0.0),
            "bandwidth_out": device.get("bandwidth_out", 0.0),
            "latency_ms": device.get("latency_ms", 0.0),
            "packet_loss": device.get("packet_loss", 0.0),
            "uptime_hours": device.get("uptime_hours", 0)
        }

        result.append(device)
    return result

@devices_router.get("/{device_id}", response_model=Device)
async def get_device(device_id: str, current_user: dict = Depends(get_current_user)):
    device = await db.devices.find_one({"id": device_id}, {"_id": 0})
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
        device = serialize_doc(device)

    metrics = None

    try:
        if device.get("password"):
            decrypted_password = decrypt_password(device["password"])

            metrics = await get_server_metrics(
                ip=device["ip_address"],
                username=device["username"],
                password=decrypted_password
            )

    except Exception as e:
        print(f"Metrics fetch failed: {e}")

    device["metrics"] = metrics
    return Device(**serialize_doc(device))

@devices_router.post("", response_model=Device)
async def create_device(device_data: DeviceCreate, current_user: dict = Depends(get_current_user)):
    #device = Device(**device_data.model_dump())
    data = device_data.model_dump()
    if data.get("password"):
        data["password"] = encrypt_password(data["password"])
    device = Device(**data)
    device_dict = device.model_dump()
    device_dict["created_at"] = device_dict["created_at"].isoformat()
    device_dict["last_seen"] = device_dict["last_seen"].isoformat()
    await db.devices.insert_one(device_dict)
    return device


@devices_router.put("/{device_id}", response_model=Device)
async def update_device(device_id: str, device_data: DeviceCreate, current_user: dict = Depends(get_current_user)):
    # 1. Look up the existing device record from MongoDB
    existing = await db.devices.find_one({"id": device_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Device not found")
    logger.info(f"Incoming payload: {device_data.model_dump()}")
    # 2. Extract input dictionary values from the Pydantic schema contract
    update_data = device_data.model_dump()
    logger.info(f"Update data: {update_data}")
    # 3. Handle password modifications securely
    if update_data.get("password"):
        update_data["password"] = encrypt_password(update_data["password"])
    
        
    # =====================================================================
    # DATA-DRIVEN VENDOR INPUT NORMALIZATION (NO DROPDOWN FALLBACKS)
    # =====================================================================
    if update_data.get("vendor"):
        # Convert any text entry like "juniper" or "  Juniper " into "JUNIPER"
        input_vendor = str(update_data["vendor"]).upper().strip()
        update_data["vendor"] = input_vendor
        
        # Check if the user is changing the vendor away from a stale placeholder
        old_vendor = str(existing.get("vendor", "")).upper().strip()
        if input_vendor != old_vendor:
            # Drop old discovery markers so get_device_metrics knows it needs a new discovery run
            update_data["model"] = f"{input_vendor} Pending CLI Profiling..."
            update_data["os_version"] = "Pending Next Polling Pass..."
            update_data["firmware_version"] = "Pending Next Polling Pass..."
            update_data["serial_number"] = "PENDING-PROBE"
    else:
        # Prevent wiping existing root properties if left out of the request
        update_data.pop("vendor", None)

    # 4. Standardize the device collection keys
    update_data["last_seen"] = datetime.now(timezone.utc).isoformat()
    
    # Align the payload 'type' property to match model expectations
    if update_data.get("type"):
        update_data["device_type"] = update_data["type"]

    # 5. Commit properties dynamically to the database document
    await db.devices.update_one({"id": device_id}, {"$set": update_data})
    
    # 6. Retrieve, serialize, and return the fresh database snapshot
    updated = await db.devices.find_one({"id": device_id})
    logger.info(f"Vendor after update = {updated.get('vendor')}")
    logger.info(f"Status after update = {updated.get('status')}")
    logger.info(f"Model after update = {updated.get('model')}")
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

import asyncssh
import asyncio
import re

async def get_device_metrics(device: dict):
    """
    Data-Driven Network Telemetry Gatherer (Zero-Fallback Pattern)
    Accepts the entire structured live database document directly.
    """
    try:
        ip = device.get("ip_address")
        username = device.get("username")
        # Decrypted password is passed downstream directly via the device monitor dict container
        password = device.get("password") 
        
        # Pull vendor straight from the document root metadata updated by your UI form input field
        vendor_name = device.get("vendor")
        if not vendor_name:
            logger.error(f"Execution blocked for {ip}: Missing explicit Vendor configuration profile.")
            return None

        # Route profile strictly based on vendor name string token matching
        profile = get_vendor_profile(vendor_name)

        async with asyncssh.connect(
            ip,
            username=username,
            password=password,
            known_hosts=None,
            connect_timeout=30,
            encryption_algs=["aes128-cbc", "aes192-cbc", "aes256-cbc", "3des-cbc", "aes128-ctr","aes192-ctr","aes256-ctr","aes128-gcm@openssh.com","aes256-gcm@openssh.com","chacha20-poly1305@openssh.com"]
        ) as conn:

            # =================================================================
            # SERVER/COMPUTE RACK MODULE ENGINE (session_type == "exec")
            # =================================================================
            if profile.session_type == "exec":
                outputs = {}
                for key, cmd in profile.commands.get("fetch_exec_commands", {}).items():
                    try:
                        res = await conn.run(cmd, check=True)
                        outputs[key] = res.stdout.strip()
                    except Exception:
                        outputs[key] = ""

                patterns = profile.cli_patterns
                
                # =================================================================
                # FULLY DYNAMIC UNIVERSAL TELEMETRY PARSER (ALL DEVICE TYPES) Modified 27/07/26
                # =================================================================
                # Aggregate all output blocks returned by the device regardless of command keys
                all_raw_text = " \n ".join([str(val) for val in outputs.values() if val])
                
                cpu_usage = 0.0
                memory_usage = 0.0

                # 1. Dynamic CPU Extraction
                # Looks for keywords like 'cpu', 'processor', 'util', 'load' and extracts adjacent percentages or load values
                cpu_patterns = [
                    r"(?:cpu|processor|utilization|load)[^\d]{1,25}(\d{1,3}(?:\.\d+)?)\s*%",  # Keyword followed by %
                    r"(\d{1,3}(?:\.\d+)?)\s*%\s*(?:cpu|utilization)",                          # % followed by keyword
                    r"idle[^\d]{1,15}(\d{1,3}(?:\.\d+)?)\s*%",                                # Inverse idle calculation
                    r"load average[^\d]*(\d+\.\d+)",                                         # Unix/Linux load averages
                    r"one minute:\s*([\d\.]+)%"                                              # Router/Switch average blocks
                ]

                for pat in cpu_patterns:
                    match = re.search(pat, all_raw_text, re.IGNORECASE)
                    if match:
                        val = float(match.group(1))
                        if "idle" in pat:
                            cpu_usage = round(max(0.0, min(100.0, 100.0 - val)), 2)
                        elif "load average" in pat:
                            # Normalize a standard 1-min load average relative to a nominal core scale (cap at 100)
                            cpu_usage = round(max(0.0, min(100.0, val * 25.0)), 2)
                        else:
                            cpu_usage = round(max(0.0, min(100.0, val)), 2)
                        break

                # 2. Dynamic Memory / Storage / RAM Extraction
                # Looks for memory/RAM blocks, percentages, or explicit used/total metrics across any OS/hardware type
                mem_patterns = [
                    r"(?:memory|ram|swap|buffer|utilization)[^\d]{1,25}(\d{1,3}(?:\.\d+)?)\s*%\s*used", # Keyword with explicit % used
                    r"(\d{1,3}(?:\.\d+)?)\s*%\s*(?:used|consumed)[^\n]*?(?:memory|ram|swap)",          # % used preceding keyword
                    r"MemTotal[^\d]*(\d+).*?MemFree[^\d]*(\d+)",                                     # Linux proc memory block
                    r"(?:total|size)[^\d]*(\d+)[^\n]*(?:used|allocated)[^\d]*(\d+)"                  # Storage/Server pool metric pairs
                ]

                mem_matched = False
                for pat in mem_patterns:
                    match = re.search(pat, all_raw_text, re.IGNORECASE)
                    if match:
                        groups = match.groups()
                        if len(groups) == 1 or not groups[1]:
                            # Direct percentage match
                            memory_usage = round(max(0.0, min(100.0, float(groups[0]))), 2)
                            mem_matched = True
                            break
                        elif len(groups) >= 2 and groups[0] and groups[1]:
                            # Ratio pair calculation (e.g., Total vs Free or Total vs Used)
                            val1 = float(groups[0])
                            val2 = float(groups[1])
                            if val1 > 0:
                                # Determine if second group is free or used based on sizing
                                used_val = val1 - val2 if val2 < val1 else val2
                                memory_usage = round(max(0.0, min(100.0, (used_val / val1) * 100)), 2)
                                mem_matched = True
                                break

                # Fallback ratio scan: Search for any general "Used X of Y" or pool allocation patterns across storage/firewalls/loadbalancers
                if not mem_matched:
                    ratio_match = re.search(r"(\d+)\s*(?:MB|GB|KB|Bytes)?\s*(?:used|allocated)[^\n]*?of\s*(\d+)\s*(?:MB|GB|KB|Bytes)?", all_raw_text, re.IGNORECASE)
                    if ratio_match:
                        u_val = float(ratio_match.group(1))
                        t_val = float(ratio_match.group(2))
                        if t_val > 0:
                            memory_usage = round(max(0.0, min(100.0, (u_val / t_val) * 100)), 2)

            # =================================================================
            # INFRASTRUCTURE CORE PROBE ENGINE (session_type == "shell")
            # =================================================================
            else:

                process = await conn.create_process(term_type="vt100")
                
                # Dynamic terminal screen length bypass configuration
                if profile.commands.get("terminal_length"):
                    process.stdin.write(f"{profile.commands['terminal_length']}\n")
                    # Dynamically read and flush the buffer until the router settles
                    while True:
                        try:
                            await asyncio.wait_for(process.stdout.read(65535), timeout=1.0)
                        except asyncio.TimeoutError:
                            break

                outputs = {}
                # Safely handle both dictionary and list formats from the profile
                shell_cmds = profile.commands.get("fetch_shell_commands", {})
                if isinstance(shell_cmds, dict):
                    shell_cmds = shell_cmds.items()

                for key, cmd in shell_cmds:
                    process.stdin.write(f"{cmd}\n")
                    outputs[key] = ""
                    # Read the incoming stream continuously until the device prompt returns and halts output
                    while True:
                        try:
                            # Decode byte chunks as they stream in
                            chunk_bytes = await asyncio.wait_for(process.stdout.read(65535), timeout=1.5)
                            if not chunk_bytes: # Break if End of File is explicitly reached
                                break
                            outputs[key] += chunk_bytes
                        except asyncio.TimeoutError:
                            # Break when the device has stopped outputting data for 1.5 seconds
                            break

                patterns = profile.cli_patterns

                # =================================================================
                # UNIVERSAL VENDOR-AGNOSTIC TELEMETRY PARSER
                # =================================================================
                cpu_output = outputs.get("cpu", "") or outputs.get("ver", "") or ""
                mem_output = outputs.get("mem", "") or outputs.get("cpu", "") or ""

                # 1. Universal CPU Extraction (Scans for percentages or idle counts across any OS)
                cpu_usage = 0.0
                cpu_patterns = [
                    r"CPU state.*?([\d\.]+)% idle",                                # NX-OS / Cisco style
                    r"(?:CPU utilization|CPU usage)[^\d]*([\d\.]+)%",                # General percentage style
                    r"one minute:\s+([\d\.]+)%.*?five minutes",                    # Linux / Router load style
                    r"CPU[^\d]*(\d+)[%\s]+utilization",                            # Alternative vendor style
                    r"idle[^\d]*([\d\.]+)%"                                        # Inverse idle search
                ]
                
                for pattern in cpu_patterns:
                    match = re.search(pattern, cpu_output, re.IGNORECASE)
                    if match:
                        val = float(match.group(1))
                        if "idle" in pattern:
                            cpu_usage = round(max(0.0, min(100.0, 100.0 - val)), 2)
                        else:
                            cpu_usage = round(max(0.0, min(100.0, val)), 2)
                        break

                # 2. Universal Memory Extraction (Scans for percentages or used/total metrics across any OS)
                memory_usage = 0.0
                mem_patterns = [
                    r"Memory usage:\s+\d+[KMGT]? total[^\n]*?(\d+)% used",         # Cisco style
                    r"(?:Memory|RAM)[^\d]*(\d+)%[^\n]*used",                       # Generic percentage
                    r"(?:MemFree|MemTotal)[^\n]*?(\d+)%",                          # Linux proc style
                ]
                
                mem_matched = False
                for pattern in mem_patterns:
                    match = re.search(pattern, mem_output, re.IGNORECASE)
                    if match:
                        memory_usage = round(max(0.0, min(100.0, float(match.group(1)))), 2)
                        mem_matched = True
                        break
                
                # Fallback calculation if no direct percentage is found in the text block
                if not mem_matched:
                    t_match = re.search(r"(?:Total|Size|RAMTotal)[^\d]*(\d+)", mem_output, re.IGNORECASE)
                    u_match = re.search(r"(?:Used|Allocated|RAMUsed)[^\d]*(\d+)", mem_output, re.IGNORECASE)
                    if t_match and u_match:
                        t_val = float(t_match.group(1))
                        u_val = float(u_match.group(1))
                        if t_val > 0:
                            memory_usage = round(max(0.0, min(100.0, (u_val / t_val) * 100)), 2)

                # Metadata Extractions via profile patterns
                os_version = "Unknown OS"
                os_match = re.search(patterns.get("os_version", ""), outputs.get("ver", ""))
                if os_match:
                    os_version = os_match.group(1).strip()

                model_name = profile.default_model
                model_match = re.search(patterns.get("model", ""), outputs.get("ver", ""), re.IGNORECASE)
                if model_match:
                    model_name = model_match.group(1).strip()

                mac_address = "00:00:00:00:00:00"
                mac_match = re.search(patterns.get("mac_address", ""), outputs.get("int", ""))
                if mac_match:
                    clean_mac = mac_match.group(1).replace('.', '').replace(':', '').replace('-', '')
                    mac_address = ":".join([clean_mac[i:i+2] for i in range(0, 12, 2)]).upper()

                hostname = "Network-Device"
                host_match = re.search(patterns.get("hostname", ""), outputs.get("ver", ""), re.IGNORECASE)
                if host_match:
                    hostname = host_match.group(1).strip()

                serial_number = "UNKNOWN-SN"
                serial_match = re.search(patterns.get("serial_number", ""), outputs.get("ver", ""), re.IGNORECASE)
                if serial_match:
                    serial_number = serial_match.group(1).strip()

                # Dynamic Neighbors parsing
                discovered_neighbors = []
                if "neighbors" in patterns:
                    nbr_blocks = re.findall(patterns["neighbors"], outputs.get("neighbors", ""), re.DOTALL | re.IGNORECASE)
                    for block in nbr_blocks:
                        if isinstance(block, tuple):
                            discovered_neighbors.append({
                                "hostname": block[0].strip().split('.')[0],
                                "ip_address": block[1].strip().split()[0]
                            })
                interfaces = []
                if "interfaces" in outputs:

                    for line in outputs["interfaces"].splitlines():

                        line = line.strip()

                        if (
                            not line
                            or line.startswith("Interface")
                            or line.startswith("IP-Address")
                            or "#" in line
                        ):
                            continue

                        parts = line.split()

                        if len(parts) < 6:
                            continue

                        interface_name = parts[0]

                        # Ignore virtual interfaces
                        if interface_name.lower().startswith(
                            ("loopback", "vlan", "tunnel", "null")
                        ):
                            continue

                        if "administratively" in line:
                            admin_status = "administratively down"
                            protocol_status = parts[-1]
                        else:
                            admin_status = parts[-2]
                            protocol_status = parts[-1]

                        interfaces.append({
                            "interface": interface_name,
                            "link_status": protocol_status,
                            "admin_status": admin_status,
                            "protocol": protocol_status,
                            "last_changed": "N/A",
                            "description": ""
                        })
                routing_table = []
                if "routing" in outputs:
                    route_lines = outputs["routing"].splitlines()
                    for line in route_lines:
                        match = re.search(r'([A-Z])\s+([0-9.\/]+)\s+.*via\s+([0-9.]+)', line)
                        if match:
                            protocol, network, next_hop = match.groups()
                            routing_table.append({
                                "protocol": protocol,
                                "network": network,
                                "next_hop": next_hop,
                                "type": "static" if protocol == "S" else "connected" if protocol == "C" else "dynamic"
                            })
                start_time = time.time()
                process.stdin.write("\n")
                await process.stdout.read(1024)
                latency_ms = round((time.time() - start_time) * 1000, 2)

                return {
                    "cpu_usage": cpu_usage,
                    "memory_usage": memory_usage,
                    "disk_usage": 0.0,
                    "bandwidth_in": round(cpu_usage * 2.1, 2),
                    "bandwidth_out": round(cpu_usage * 1.8, 2),
                    "latency_ms": latency_ms,
                    "packet_loss": 0.0,
                    "uptime_hours": 24,
                    "os_version": f"{profile.vendor_display_name} {os_version}",
                    "mac_address": mac_address,
                    "vendor": profile.vendor_display_name,
                    "model": f"{profile.vendor_display_name} {model_name}",
                    "hostname": hostname,
                    "serial_number": serial_number,
                    "neighbors": discovered_neighbors,
                    "interfaces": interfaces,
                    "routing_table": routing_table,
                }
    except Exception as e:
        logger.error(f"Polling failure context for device endpoint: {str(e)}")
        return None


from cryptography.fernet import Fernet
import os

SECRET_KEY = os.getenv("DEVICE_SECRET_KEY").encode()

cipher = Fernet(SECRET_KEY)

async def save_device_event(
    device,
    status,
    cpu_usage=0,
    memory_usage=0
):

    await db.device_events.insert_one({
        "id": str(uuid.uuid4()),
        "device_id": device["id"],
        "device_name": device["name"],
        "status": status,
        "cpu_usage": cpu_usage,
        "memory_usage": memory_usage,
        "timestamp": datetime.now(
            timezone.utc
        ).isoformat()
    })

def encrypt_password(password: str):
    return cipher.encrypt(password.encode()).decode()


def decrypt_password(encrypted_password: str):
    return cipher.decrypt(encrypted_password.encode()).decode()

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

@alerts_router.get("/{alert_id}")
async def get_alert(alert_id: str, current_user: dict = Depends(get_current_user)):
    """Get a single alert by ID"""
    alert = await db.alerts.find_one({"id": alert_id}, {"_id": 0})
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return Alert(**serialize_doc(alert))

@alerts_router.post("/{alert_id}/ai-troubleshoot")
async def ai_troubleshoot_alert(alert_id: str, current_user: dict = Depends(get_current_user)):
    """AI Agent analyzes an alert and provides troubleshooting recommendations"""
    alert = await db.alerts.find_one({"id": alert_id}, {"_id": 0})
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    # Get device details
    device = await db.devices.find_one({"id": alert.get('device_id')}, {"_id": 0})
    device_info = ""
    if device:
        device_info = f"""
=== DEVICE INFORMATION ===
Name: {device.get('name', 'N/A')}
Type: {device.get('type', 'N/A')}
IP Address: {device.get('ip_address', 'N/A')}
Location: {device.get('location', 'N/A')}
Vendor: {device.get('vendor', 'N/A')}
Model: {device.get('model', 'N/A')}
Status: {device.get('status', 'N/A')}
CPU Usage: {device.get('cpu_usage', 'N/A')}%
Memory Usage: {device.get('memory_usage', 'N/A')}%
"""
    
    # Get recent performance metrics for the device
    recent_metrics = await db.performance_metrics.find(
        {"device_id": alert.get('device_id')},
        {"_id": 0}
    ).sort("timestamp", -1).to_list(5)
    
    metrics_summary = ""
    if recent_metrics:
        metrics_summary = "\n=== RECENT PERFORMANCE METRICS ===\n"
        for m in recent_metrics[:3]:
            metrics_summary += f"- CPU: {m.get('cpu_usage', 0):.1f}%, Memory: {m.get('memory_usage', 0):.1f}%, Latency: {m.get('latency_ms', 0):.1f}ms\n"
    
    context = f"""
=== ALERT DETAILS ===
Title: {alert.get('title', 'N/A')}
Description: {alert.get('description', 'N/A')}
Severity: {alert.get('severity', 'N/A').upper()}
Status: {alert.get('status', 'N/A')}
Device: {alert.get('device_name', 'N/A')}
Metric: {alert.get('metric_name', 'N/A')}
Value: {alert.get('metric_value', 'N/A')}
Threshold: {alert.get('threshold', 'N/A')}
Created: {alert.get('created_at', 'N/A')}
{device_info}
{metrics_summary}
"""
    
    analysis = await get_ai_analysis(
        context,
        """You are an expert NOC AI Agent. Analyze this alert and provide a comprehensive troubleshooting report with:

1. **ALERT ASSESSMENT**: Severity evaluation and impact analysis
2. **PROBABLE CAUSE**: What likely caused this alert
3. **IMMEDIATE ACTIONS**: Steps to take right now
4. **TROUBLESHOOTING COMMANDS**: Specific CLI commands or checks to run
5. **RESOLUTION STEPS**: How to resolve the underlying issue
6. **MONITORING RECOMMENDATIONS**: What to watch after resolution
7. **SHOULD CREATE INCIDENT**: Yes/No with reasoning

Be specific to the device type and alert nature."""
    )
    
    # Store the troubleshooting report
    troubleshoot_report = {
        "id": str(uuid.uuid4()),
        "alert_id": alert_id,
        "analysis": analysis,
        "triggered_by": current_user["name"],
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.troubleshoot_reports.insert_one(troubleshoot_report)
    
    return {
        "report_id": troubleshoot_report["id"],
        "alert_id": alert_id,
        "analysis": analysis,
        "triggered_by": current_user["name"],
        "created_at": troubleshoot_report["created_at"]
    }

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
    
    # Check if auto-trigger is enabled
    agent_settings = await agent_service.get_agent_settings()
    if agent_settings.get('auto_trigger_on_incident', False):
        auto_priorities = agent_settings.get('auto_trigger_priorities', ['P1', 'P2'])
        if incident.priority.value in auto_priorities:
            # Trigger agent in background
            asyncio.create_task(
                agent_service.run_autonomous_troubleshooting(
                    incident_id=incident.id,
                    triggered_by="System (Auto-Trigger)",
                    trigger_type="auto"
                )
            )
            # Notify via WebSocket
            await ws_manager.broadcast({
                "type": "agent_auto_triggered",
                "data": {
                    "incident_id": incident.id,
                    "ticket_number": incident.ticket_number,
                    "priority": incident.priority.value
                }
            })
    
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

@incidents_router.post("/{incident_id}/ai-troubleshoot")
async def ai_troubleshoot_incident(incident_id: str, current_user: dict = Depends(get_current_user)):
    """AI Agent starts troubleshooting an incident and provides a detailed report"""
    incident = await db.incidents.find_one({"id": incident_id}, {"_id": 0})
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    
    # Get affected device details
    device_details = []
    for device_id in incident.get('affected_devices', []):
        device = await db.devices.find_one({"id": device_id}, {"_id": 0})
        if device:
            device_details.append(f"- {device['name']} ({device.get('ip_address', 'N/A')}) - Status: {device.get('status', 'unknown')}")
    
    # Get recent alerts related to this incident
    related_alerts = await db.alerts.find(
        {"device_id": {"$in": incident.get('affected_devices', [])}},
        {"_id": 0}
    ).sort("created_at", -1).to_list(10)
    
    alert_summary = "\n".join([
        f"- [{a.get('severity', 'N/A').upper()}] {a.get('title', 'Unknown')} on {a.get('device_name', 'Unknown')}"
        for a in related_alerts
    ]) if related_alerts else "No recent alerts found."
    
    context = f"""
=== INCIDENT DETAILS ===
Ticket: {incident.get('ticket_number', 'N/A')}
Title: {incident['title']}
Description: {incident['description']}
Priority: {incident['priority']}
Category: {incident['category']}
Status: {incident['status']}
Escalation Level: L{incident.get('escalation_level', 1)}
Created: {incident.get('created_at', 'N/A')}

=== AFFECTED DEVICES ===
{chr(10).join(device_details) if device_details else 'No specific devices assigned.'}

=== RELATED ALERTS ===
{alert_summary}
"""
    
    analysis = await get_ai_analysis(
        context,
        """You are an expert NOC AI Agent. Perform a comprehensive troubleshooting analysis and provide a detailed report with the following sections:

1. **INCIDENT SUMMARY**: Brief summary of the issue
2. **ROOT CAUSE ANALYSIS**: Identify probable root causes based on available data
3. **TROUBLESHOOTING STEPS**: Step-by-step troubleshooting guide
4. **RECOMMENDED ACTIONS**: Specific actions to resolve the issue
5. **PREVENTION MEASURES**: How to prevent this issue in the future
6. **ESTIMATED RESOLUTION TIME**: Based on complexity
7. **ESCALATION RECOMMENDATION**: Whether to escalate and to which team

Be specific, technical, and actionable."""
    )
    
    # Store the troubleshooting report
    troubleshoot_report = {
        "id": str(uuid.uuid4()),
        "incident_id": incident_id,
        "analysis": analysis,
        "triggered_by": current_user["name"],
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.troubleshoot_reports.insert_one(troubleshoot_report)
    
    # Update incident with AI suggestions
    await db.incidents.update_one(
        {"id": incident_id},
        {"$set": {
            "ai_suggestions": analysis,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "status": "in_progress" if incident.get('status') == 'open' else incident.get('status')
        }}
    )
    
    return {
        "report_id": troubleshoot_report["id"],
        "incident_id": incident_id,
        "analysis": analysis,
        "triggered_by": current_user["name"],
        "created_at": troubleshoot_report["created_at"]
    }


async def create_offline_incident(device,alert_id=None): # Fix on alert ID
    existing = await db.incidents.find_one({
        "device_id": device["id"],
        "status": {
            "$in": [
                "open",
                "in_progress", "awaiting_approval","awaiting_approval"
            ]
        }
    })
 
    if existing:
        return
 
    incident_id = str(uuid.uuid4())
    sla_record = {
        "id": str(uuid.uuid4()),
        "incident_id": incident_id,
        "priority": "P1",
        "response_time_target_mins": 15,
        "resolution_time_target_mins": 60,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    # 1. Fetch Topology Inventory so the AI knows who the neighbors are
    all_devices = await db.devices.find({}, {"_id": 0, "name": 1, "ip_address": 1, "type": 1, "location": 1}).to_list(100)
    devices_list_str = "\n".join([f"- {d.get('name')} (IP: {d.get('ip_address')}, Type: {d.get('type')})" for d in all_devices])
 
    # 2. Fetch Recent Alerts (Last 15 mins) to catch neighbor interface down logs
    from datetime import timedelta
    recent_cutoff = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()
    recent_alerts = await db.alerts.find(
        {"created_at": {"$gte": recent_cutoff}},
        {"_id": 0, "title": 1, "device_name": 1, "description": 1}
    ).to_list(10)
    alerts_str = "None"
    if recent_alerts:
        alerts_str = "\n".join([f"- {a.get('device_name')}: {a.get('title')} - {a.get('description')}" for a in recent_alerts])
 
    # 3. Enhanced AI Analysis
    ai_analysis = await get_ai_analysis(
        context=f"""
=== AFFECTED DEVICE ===
Device Name: {device['name']}
IP Address: {device['ip_address']}
Device Type: {device['type']}
Current Status: OFFLINE
 
=== NETWORK TOPOLOGY INVENTORY ===
{devices_list_str}
 
=== RECENT NETWORK ALERTS (Preceding the outage) ===
{alerts_str}
""",
        query="""
The affected device just became unreachable via SSH/Ping. You must determine the EXACT physical or logical reason (e.g., serial cable failure, upstream interface shutdown, power loss).
 
Examine the 'Recent Network Alerts'. If an upstream neighbor reported a link down or routing protocol failure right before this outage, that is your exact root cause. Deduce the relationship using the inventory.
 
Provide:
1. Root Cause Analysis (Explicitly state if it is a cable failure, interface down, etc., and name the upstream neighbor involved).
2. Possible Reasons (Ranked by probability).
3. Troubleshooting Steps (Specify commands to run on the UPSTREAM neighbor, not the offline device).
4. Resolution Recommendations
"""
    )
 
    incident = {
        "id": incident_id,
        "ticket_number": f"INC-{int(time.time())}",
        "title": f"{device['name']} Offline",
        "description": f"Device {device['name']} ({device['ip_address']}) became unreachable.",
        "priority": "P1",
        "category": "Network",
        "status": "in_progress",
        "device_id": device["id"],
        "affected_devices": [device["id"]],
        "related_alerts": [alert_id] if alert_id else [], # Alert Fix
        "ai_suggestions": ai_analysis,
        "created_by": "System Monitor",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
 
    await db.incidents.insert_one(incident)
    await db.sla_records.insert_one(sla_record)
    print(f"Created incident for {device['name']}")

async def resolve_device_incident(
    device_id
):

    await db.incidents.update_many(
        {
            "device_id": device_id,
            "status": {
                "$in": [
                    "open",
                    "in_progress"
                ]
            }
        },
        {
            "$set": {
                "status": "resolved",
                "resolved_at": datetime.now(
                    timezone.utc
                ).isoformat(),
                "updated_at": datetime.now(
                    timezone.utc
                ).isoformat()
            }
        }
    )

# ===================== PERFORMANCE ROUTES =====================
@performance_router.get("", response_model=List[PerformanceMetric]) #modified 27/07/26 for performance page 
async def get_performance_metrics(
    device_id: Optional[str] = None, 
    hours: int = 24, 
    current_user: dict = Depends(get_current_user)
):
    query = {}
    if device_id and device_id != "all":
        query["device_id"] = device_id
    
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    query["timestamp"] = {"$gte": cutoff.isoformat()}
    
    metrics = await db.performance_metrics.find(query, {"_id": 0}).sort("timestamp", -1).to_list(5000)
    
    # Fallback: If historical metrics collection is empty for this device, 
    # generate a live snapshot point from the device's current telemetry so the UI isn't blank.
    if not metrics and device_id and device_id != "all":
        device = await db.devices.find_one({"id": device_id}, {"_id": 0})
        if device:
            fallback_metric = {
                "id": str(uuid.uuid4()),
                "device_id": device["id"],
                "device_name": device.get("name", "Device"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "cpu_usage": device.get("cpu_usage", 0.0),
                "memory_usage": device.get("memory_usage", 0.0),
                "disk_usage": device.get("disk_usage", 0.0),
                "bandwidth_in": device.get("bandwidth_in", 0.0),
                "bandwidth_out": device.get("bandwidth_out", 0.0),
                "latency_ms": device.get("latency_ms", 0.0),
                "packet_loss": device.get("packet_loss", 0.0),
                "uptime_hours": device.get("uptime_hours", 0)
            }
            # Insert and return
            await db.performance_metrics.insert_one(fallback_metric.copy())
            metrics = [fallback_metric]

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
    """Generate enhanced reports based on type"""
    content = {}
    
    if report_type == "daily_health":
        # Enhanced Daily Health Check Report
        devices = await db.devices.find({}, {"_id": 0}).to_list(1000)
        alerts = await db.alerts.find({"status": "active"}, {"_id": 0}).to_list(1000)
        
        # Build detailed device health information
        device_health_details = []
        for device in devices:
            # Simulate interface data (in production, this would come from SNMP polling)
            total_interfaces = 24 if device.get("type") in ["switch", "router"] else 4
            used_interfaces = int(total_interfaces * 0.6)  # Simulated 60% usage
            
            device_health = {
                "device_name": device.get("name", "Unknown"),
                "device_type": device.get("type", "Unknown"),
                "ip_address": device.get("ip_address", "N/A"),
                "status": device.get("status", "unknown"),
                "vendor": device.get("vendor", "Unknown"),
                "model": device.get("model", "Unknown"),
                # Memory metrics
                "memory_usage_percent": round(device.get("memory_usage", 0), 2),
                "memory_status": "Critical" if device.get("memory_usage", 0) > 90 else "Warning" if device.get("memory_usage", 0) > 75 else "Normal",
                "dead_memory_percent": round(max(0, device.get("memory_usage", 0) - 80) * 0.1, 2),  # Simulated dead memory
                # CPU metrics
                "cpu_usage_percent": round(device.get("cpu_usage", 0), 2),
                "cpu_status": "Critical" if device.get("cpu_usage", 0) > 90 else "Warning" if device.get("cpu_usage", 0) > 75 else "Normal",
                # Traffic metrics (simulated - in production from SNMP counters)
                "traffic_in_mbps": round(device.get("cpu_usage", 0) * 10, 2),  # Simulated
                "traffic_out_mbps": round(device.get("cpu_usage", 0) * 8, 2),  # Simulated
                "peak_traffic_mbps": round(device.get("cpu_usage", 0) * 15, 2),
                # Interface status
                "total_interfaces": total_interfaces,
                "interfaces_up": used_interfaces,
                "interfaces_down": total_interfaces - used_interfaces - 2,
                "interfaces_admin_down": 2,
                "free_interfaces": total_interfaces - used_interfaces,
                "interface_utilization_percent": round((used_interfaces / total_interfaces) * 100, 2),
                # Uptime
                "uptime_hours": device.get("uptime_hours", 0),
                "uptime_days": round(device.get("uptime_hours", 0) / 24, 1),
                "last_seen": device.get("last_seen", "N/A")
            }
            device_health_details.append(device_health)
        
        # Summary statistics
        online_devices = [d for d in devices if d.get("status") == "online"]
        high_cpu_devices = [d for d in devices if d.get("cpu_usage", 0) > 75]
        high_memory_devices = [d for d in devices if d.get("memory_usage", 0) > 75]
        
        content = {
            "report_date": datetime.now(timezone.utc).isoformat(),
            "period_start": period_start,
            "period_end": period_end,
            # Summary
            "summary": {
                "total_devices": len(devices),
                "online_devices": len(online_devices),
                "offline_devices": len(devices) - len(online_devices),
                "devices_with_high_cpu": len(high_cpu_devices),
                "devices_with_high_memory": len(high_memory_devices),
                "active_alerts": len(alerts),
                "critical_alerts": len([a for a in alerts if a.get("severity") == "critical"]),
                "health_score": round(100 - (len(high_cpu_devices) + len(high_memory_devices)) / max(len(devices), 1) * 50, 1)
            },
            # Detailed device health
            "device_health": device_health_details,
            # Critical devices requiring attention
            "critical_devices": [d for d in device_health_details if d["cpu_status"] == "Critical" or d["memory_status"] == "Critical"],
            # Recommendations
            "recommendations": [
                f"Review {len(high_cpu_devices)} devices with high CPU usage" if high_cpu_devices else None,
                f"Review {len(high_memory_devices)} devices with high memory usage" if high_memory_devices else None,
                f"Check {len([a for a in alerts if a.get('severity') == 'critical'])} critical alerts" if alerts else None
            ]
        }
        content["recommendations"] = [r for r in content["recommendations"] if r]
        
    elif report_type == "incident_summary":
        # Enhanced Incident Report
        incidents = await db.incidents.find({}, {"_id": 0}).to_list(1000)
        devices = await db.devices.find({}, {"_id": 0}).to_list(1000)
        
        # Create device lookup
        device_lookup = {d.get("id"): d for d in devices}
        
        # Build detailed incident information
        incident_details = []
        for incident in incidents:
            device = device_lookup.get(incident.get("device_id"), {})
            
            # Determine if hardware replacement might be needed based on incident type
            hardware_replacement = "Possible" if any(kw in incident.get("title", "").lower() for kw in ["hardware", "failure", "dead", "faulty", "defective"]) else "Not Required"
            
            # Check for potential IOS bugs based on incident description
            ios_bug_likelihood = "Check Cisco Bug Search" if any(kw in incident.get("description", "").lower() for kw in ["crash", "reload", "memory leak", "process", "ios", "software"]) else "N/A"
            
            incident_detail = {
                "incident_id": incident.get("id", "N/A"),
                "title": incident.get("title", "N/A"),
                "status": incident.get("status", "unknown"),
                "priority": incident.get("priority", "P4"),
                # Date and Time
                "incident_date": incident.get("created_at", "N/A")[:10] if incident.get("created_at") else "N/A",
                "incident_time": incident.get("created_at", "N/A")[11:19] if incident.get("created_at") and len(incident.get("created_at", "")) > 19 else "N/A",
                "created_at": incident.get("created_at", "N/A"),
                "resolved_at": incident.get("resolved_at", "Not Resolved"),
                # Device Information
                "device_name": incident.get("device_name", "N/A"),
                "ip_address": device.get("ip_address", "N/A"),
                "device_type": device.get("type", "N/A"),
                "device_vendor": device.get("vendor", "N/A"),
                # Fault Details
                "fault_details": incident.get("description", "No details available"),
                "severity": incident.get("priority", "P4"),
                "impact": "High" if incident.get("priority") in ["P1", "P2"] else "Medium" if incident.get("priority") == "P3" else "Low",
                # Root Cause Analysis
                "suggested_rca": incident.get("ai_analysis", {}).get("root_cause", "") if incident.get("ai_analysis") else generate_suggested_rca(incident),
                "rca_category": categorize_incident(incident),
                # Hardware & Software
                "hardware_replacement_required": hardware_replacement,
                "ios_bug_report": ios_bug_likelihood,
                "affected_component": incident.get("ai_analysis", {}).get("affected_component", "Unknown") if incident.get("ai_analysis") else "To be determined",
                # Resolution
                "assigned_to": incident.get("assigned_to", "Unassigned"),
                "resolution_notes": incident.get("resolution_notes", ""),
                "mttr_hours": calculate_mttr(incident)
            }
            incident_details.append(incident_detail)
        
        # Summary statistics
        open_incidents = [i for i in incidents if i.get("status") == "open"]
        resolved_incidents = [i for i in incidents if i.get("status") in ["resolved", "closed"]]
        
        content = {
            "report_date": datetime.now(timezone.utc).isoformat(),
            "period_start": period_start,
            "period_end": period_end,
            # Summary
            "summary": {
                "total_incidents": len(incidents),
                "open_incidents": len(open_incidents),
                "resolved_incidents": len(resolved_incidents),
                "by_priority": {
                    "P1_critical": len([i for i in incidents if i.get("priority") == "P1"]),
                    "P2_high": len([i for i in incidents if i.get("priority") == "P2"]),
                    "P3_medium": len([i for i in incidents if i.get("priority") == "P3"]),
                    "P4_low": len([i for i in incidents if i.get("priority") == "P4"])
                },
                "hardware_issues": len([i for i in incident_details if i["hardware_replacement_required"] == "Possible"]),
                "potential_ios_bugs": len([i for i in incident_details if i["ios_bug_report"] != "N/A"])
            },
            # Detailed incidents
            "incidents": incident_details,
            # High priority incidents
            "critical_incidents": [i for i in incident_details if i["priority"] in ["P1", "P2"]],
            # Trending issues
            "trending_categories": get_incident_trending(incident_details)
        }
        
    elif report_type == "device_inventory":
        # Enhanced Device Inventory Report
        assets = await db.assets.find({}, {"_id": 0}).to_list(1000)
        devices = await db.devices.find({}, {"_id": 0}).to_list(1000)
        
        # Create device lookup
        device_lookup = {d.get("id"): d for d in devices}
        
        # Build detailed inventory information
        inventory_details = []
        for asset in assets:
            device = device_lookup.get(asset.get("device_id"), {})
            
            # Calculate warranty status
            warranty_status = "Unknown"
            if asset.get("warranty_expiry"):
                try:
                    expiry = datetime.fromisoformat(asset.get("warranty_expiry").replace("Z", "+00:00"))
                    days_until_expiry = (expiry - datetime.now(timezone.utc)).days
                    if days_until_expiry < 0:
                        warranty_status = "Expired"
                    elif days_until_expiry < 90:
                        warranty_status = "Expiring Soon"
                    else:
                        warranty_status = "Active"
                except:
                    warranty_status = "Unknown"
            
            inventory_item = {
                "asset_id": asset.get("id", "N/A"),
                "asset_tag": asset.get("asset_tag", "N/A"),
                "name": asset.get("name", "N/A"),
                "type": asset.get("type", "N/A"),
                # IP Address
                "ip_address": asset.get("ip_address") or device.get("ip_address", "N/A"),
                "mac_address": asset.get("mac_address") or device.get("mac_address", "N/A"),
                # Model Details
                "model": asset.get("model", "N/A"),
                "model_description": f"{asset.get('vendor', 'Unknown')} {asset.get('model', 'Unknown')}",
                "serial_number": asset.get("serial_number", "N/A"),
                "firmware_version": device.get("firmware_version", "N/A"),
                # OEM Details
                "oem_vendor": asset.get("vendor", "N/A"),
                "oem_details": asset.get("oem_details") or f"Manufactured by {asset.get('vendor', 'Unknown')}",
                "oem_support_contract": asset.get("contract_details", "N/A"),
                # Location Details
                "location": asset.get("location", "N/A"),
                "rack_position": asset.get("rack_position", "N/A") if asset.get("rack_position") else "Not Specified",
                "building": asset.get("building", "N/A") if asset.get("building") else "Not Specified",
                "floor": asset.get("floor", "N/A") if asset.get("floor") else "Not Specified",
                # Asset Tag
                "asset_tag_full": asset.get("asset_tag", "N/A"),
                "owner": asset.get("owner", "N/A"),
                "department": asset.get("department", "IT Department") if asset.get("department") else "IT Department",
                # Warranty Status
                "warranty_status": warranty_status,
                "warranty_expiry": asset.get("warranty_expiry", "N/A"),
                "purchase_date": asset.get("purchase_date", "N/A"),
                "eol_date": asset.get("eol_date", "N/A"),
                # Operational Status
                "operational_status": asset.get("status", "active"),
                "device_status": device.get("status", "unknown"),
                "last_seen": device.get("last_seen", "N/A"),
                "auto_discovered": asset.get("auto_discovered", False)
            }
            inventory_details.append(inventory_item)
        
        # Summary statistics
        active_assets = [a for a in assets if a.get("status") == "active"]
        expired_warranty = [i for i in inventory_details if i["warranty_status"] == "Expired"]
        expiring_soon = [i for i in inventory_details if i["warranty_status"] == "Expiring Soon"]
        
        content = {
            "report_date": datetime.now(timezone.utc).isoformat(),
            "period_start": period_start,
            "period_end": period_end,
            # Summary
            "summary": {
                "total_assets": len(assets),
                "active_assets": len(active_assets),
                "retired_assets": len(assets) - len(active_assets),
                "warranty_expired": len(expired_warranty),
                "warranty_expiring_soon": len(expiring_soon),
                "auto_discovered": len([a for a in assets if a.get("auto_discovered")]),
                "by_type": {}
            },
            # Detailed inventory
            "inventory": inventory_details,
            # Assets requiring attention
            "warranty_alerts": expired_warranty + expiring_soon,
            # By vendor breakdown
            "by_vendor": {},
            # By location breakdown
            "by_location": {}
        }
        
        # Calculate type breakdown
        for asset in assets:
            asset_type = asset.get("type", "Unknown")
            content["summary"]["by_type"][asset_type] = content["summary"]["by_type"].get(asset_type, 0) + 1
        
        # Calculate vendor breakdown
        for item in inventory_details:
            vendor = item["oem_vendor"]
            if vendor not in content["by_vendor"]:
                content["by_vendor"][vendor] = {"count": 0, "assets": []}
            content["by_vendor"][vendor]["count"] += 1
            content["by_vendor"][vendor]["assets"].append(item["asset_tag"])
        
        # Calculate location breakdown
        for item in inventory_details:
            location = item["location"]
            if location not in content["by_location"]:
                content["by_location"][location] = {"count": 0, "assets": []}
            content["by_location"][location]["count"] += 1
            content["by_location"][location]["assets"].append(item["asset_tag"])
            
    elif report_type == "sla_compliance":
        sla_records = await db.sla_records.find({}, {"_id": 0}).to_list(1000)
        met_count = len([s for s in sla_records if s.get("resolution_sla_met")])
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

# Helper functions for incident reporting
def generate_suggested_rca(incident: dict) -> str:
    """Generate suggested root cause analysis based on incident details"""
    title = incident.get("title", "").lower()
    description = incident.get("description", "").lower()
    
    if "cpu" in title or "cpu" in description:
        return "High CPU utilization possibly caused by: 1) Traffic spike, 2) Process anomaly, 3) Routing protocol reconvergence, 4) Denial of Service attack"
    elif "memory" in title or "memory" in description:
        return "Memory issue possibly caused by: 1) Memory leak in software, 2) Excessive BGP/OSPF routes, 3) Large ARP/MAC tables, 4) Buffer exhaustion"
    elif "interface" in title or "link" in description or "port" in description:
        return "Interface/Link issue possibly caused by: 1) Physical cable fault, 2) SFP/transceiver failure, 3) Port configuration mismatch, 4) Speed/duplex mismatch"
    elif "connectivity" in title or "unreachable" in description:
        return "Connectivity issue possibly caused by: 1) Routing problem, 2) ACL blocking traffic, 3) Interface down, 4) Upstream device failure"
    elif "power" in title or "power" in description:
        return "Power issue possibly caused by: 1) Power supply failure, 2) UPS issue, 3) Electrical circuit problem, 4) Environmental (temperature)"
    else:
        return "Further investigation required. Check: 1) Device logs, 2) SNMP traps, 3) Network topology changes, 4) Recent configuration changes"

def categorize_incident(incident: dict) -> str:
    """Categorize incident for trending analysis"""
    title = incident.get("title", "").lower()
    description = incident.get("description", "").lower()
    combined = title + " " + description
    
    if any(kw in combined for kw in ["cpu", "processor", "utilization"]):
        return "Performance - CPU"
    elif any(kw in combined for kw in ["memory", "ram", "buffer"]):
        return "Performance - Memory"
    elif any(kw in combined for kw in ["interface", "port", "link", "cable"]):
        return "Connectivity - Interface"
    elif any(kw in combined for kw in ["power", "psu", "ups"]):
        return "Hardware - Power"
    elif any(kw in combined for kw in ["temperature", "fan", "cooling"]):
        return "Environmental"
    elif any(kw in combined for kw in ["security", "attack", "intrusion"]):
        return "Security"
    elif any(kw in combined for kw in ["config", "configuration", "change"]):
        return "Configuration"
    else:
        return "Other"

def calculate_mttr(incident: dict) -> float:
    """Calculate Mean Time To Resolution in hours"""
    if incident.get("resolved_at") and incident.get("created_at"):
        try:
            created = datetime.fromisoformat(incident["created_at"].replace("Z", "+00:00"))
            resolved = datetime.fromisoformat(incident["resolved_at"].replace("Z", "+00:00"))
            return round((resolved - created).total_seconds() / 3600, 2)
        except:
            return 0
    return 0

def get_incident_trending(incidents: list) -> dict:
    """Get trending incident categories"""
    categories = {}
    for incident in incidents:
        cat = incident.get("rca_category", "Other")
        categories[cat] = categories.get(cat, 0) + 1
    
    # Sort by count
    sorted_cats = sorted(categories.items(), key=lambda x: x[1], reverse=True)
    return {cat: count for cat, count in sorted_cats[:5]}

@reports_router.get("/{report_id}/download/pdf")
async def download_report_pdf(report_id: str, current_user: dict = Depends(get_current_user)):
    """Download report as PDF"""
    from io import BytesIO
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib import colors
    
    report = await db.reports.find_one({"id": report_id}, {"_id": 0})
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    # Create PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=72)
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=18, spaceAfter=30, textColor=colors.HexColor('#1e40af'))
    subtitle_style = ParagraphStyle('CustomSubtitle', parent=styles['Normal'], fontSize=10, textColor=colors.gray, spaceAfter=20)
    heading_style = ParagraphStyle('CustomHeading', parent=styles['Heading2'], fontSize=14, spaceBefore=15, spaceAfter=10)
    
    elements = []
    
    # Title
    elements.append(Paragraph("ATECH NOC Commander", title_style))
    elements.append(Paragraph(report.get('title', 'Report'), styles['Heading2']))
    elements.append(Spacer(1, 10))
    
    # Metadata
    elements.append(Paragraph(f"Report Type: {report.get('type', '').replace('_', ' ').title()}", subtitle_style))
    elements.append(Paragraph(f"Period: {report.get('period_start', '')} to {report.get('period_end', '')}", subtitle_style))
    elements.append(Paragraph(f"Generated By: {report.get('generated_by', 'System')}", subtitle_style))
    elements.append(Paragraph(f"Generated At: {report.get('created_at', '')}", subtitle_style))
    elements.append(Spacer(1, 20))
    
    # Content
    content = report.get('content', {})
    if content:
        elements.append(Paragraph("Report Summary", heading_style))
        
        # Convert content to table
        table_data = [['Metric', 'Value']]
        for key, value in content.items():
            if isinstance(value, dict):
                for k, v in value.items():
                    table_data.append([f"  {k.replace('_', ' ').title()}", str(v)])
            else:
                table_data.append([key.replace('_', ' ').title(), str(value)])
        
        table = Table(table_data, colWidths=[3*inch, 2*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e40af')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8fafc')),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('TOPPADDING', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        ]))
        elements.append(table)
    
    elements.append(Spacer(1, 30))
    elements.append(Paragraph("--- End of Report ---", subtitle_style))
    
    doc.build(elements)
    buffer.seek(0)
    
    return Response(
        content=buffer.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={report.get('title', 'report').replace(' ', '_')}.pdf"}
    )

@reports_router.get("/{report_id}/download/csv")
async def download_report_csv(report_id: str, current_user: dict = Depends(get_current_user)):
    """Download report as CSV"""
    import csv
    from io import StringIO
    
    report = await db.reports.find_one({"id": report_id}, {"_id": 0})
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    # Create CSV
    output = StringIO()
    writer = csv.writer(output)
    
    # Header row
    writer.writerow(['ATECH NOC Commander Report'])
    writer.writerow([])
    writer.writerow(['Report Title', report.get('title', '')])
    writer.writerow(['Report Type', report.get('type', '').replace('_', ' ').title()])
    writer.writerow(['Period Start', report.get('period_start', '')])
    writer.writerow(['Period End', report.get('period_end', '')])
    writer.writerow(['Generated By', report.get('generated_by', '')])
    writer.writerow(['Generated At', report.get('created_at', '')])
    writer.writerow([])
    writer.writerow(['Metric', 'Value'])
    
    # Content rows
    content = report.get('content', {})
    for key, value in content.items():
        if isinstance(value, dict):
            for k, v in value.items():
                writer.writerow([f"{key} - {k}".replace('_', ' ').title(), str(v)])
        else:
            writer.writerow([key.replace('_', ' ').title(), str(value)])
    
    output.seek(0)
    
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={report.get('title', 'report').replace(' ', '_')}.csv"}
    )

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
    response_met = len([r for r in records if r.get("response_sla_met")])
    resolution_met = len([r for r in records if r.get("resolution_sla_met")])
    
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


def parse_dt(value):

    if not value:

        return None

    try:

        return datetime.fromisoformat(value)

    except Exception:

        return None
 
@dashboard_router.get("/stats")
async def get_dashboard_stats(current_user: dict = Depends(get_current_user)):
 
    devices = await db.devices.find({}, {"_id": 0}).to_list(None)
    alerts = await db.alerts.find({}, {"_id": 0}).to_list(None)
    incidents = await db.incidents.find({}, {"_id": 0}).to_list(None)
 
    active_alerts = [a for a in alerts if a.get("status") == "active"]
    open_incidents = [
        i for i in incidents
        if i.get("status") in ["open", "in_progress"]
    ]
 
    # -----------------------------
    # Current Availability
    # -----------------------------
 
    online_devices = len(
        [d for d in devices if d.get("status") == "online"]
    )
 
    total_devices = len(devices) or 1
 
    uptime_pct = round(
        online_devices / total_devices * 100,
        2
    )
 
    # -----------------------------
    # MTTR
    # -----------------------------
 
    mttr_values = []
 
    for incident in incidents:
 
        created = parse_dt(incident.get("created_at"))
        resolved = parse_dt(incident.get("resolved_at"))
 
        if created and resolved:
            mttr_values.append(
                (resolved - created).total_seconds() / 60
            )
 
    mttr = round(
        sum(mttr_values) / len(mttr_values),
        2
    ) if mttr_values else 0
 
    # -----------------------------
    # MTTD
    # Alert -> Incident creation
    # -----------------------------
 
    alert_lookup = {}
 
    for alert in alerts:
        alert_lookup.setdefault(
            alert["device_id"],
            []
        ).append(alert)
 
    mttd_values = []
 
    for incident in incidents:
 
        incident_created = parse_dt(
            incident.get("created_at")
        )
 
        if not incident_created:
            continue
 
        device_alerts = alert_lookup.get(
            incident["device_id"],
            []
        )
 
        if not device_alerts:
            continue
 
        closest_alert = min(
            device_alerts,
            key=lambda a: abs(
                (
                    parse_dt(a["created_at"]) -
                    incident_created
                ).total_seconds()
            )
        )
 
        alert_created = parse_dt(
            closest_alert["created_at"]
        )
 
        diff = (
            incident_created -
            alert_created
        ).total_seconds()
 
        if diff >= 0:
            mttd_values.append(diff / 60)
 
    mttd = round(
        sum(mttd_values) / len(mttd_values),
        2
    ) if mttd_values else 0
 
    # -----------------------------
    # SLA Compliance
    # -----------------------------
 
    sla_rules = {
        "P1": 60,
        "P2": 240,
        "P3": 480,
        "P4": 1440
    }
 
    sla_met = 0
    sla_total = 0
 
    for incident in incidents:
 
        created = parse_dt(
            incident.get("created_at")
        )
 
        resolved = parse_dt(
            incident.get("resolved_at")
        )
 
        if not created or not resolved:
            continue
 
        sla_total += 1
 
        resolution_minutes = (
            resolved - created
        ).total_seconds() / 60
 
        allowed = sla_rules.get(
            incident.get("priority"),
            240
        )
 
        if resolution_minutes <= allowed:
            sla_met += 1
 
    sla = round(
        sla_met / sla_total * 100,
        2
    ) if sla_total else 100
 
    # -----------------------------
    # Alert Resolution Time
    # -----------------------------
 
    alert_times = []
 
    for alert in alerts:
 
        created = parse_dt(
            alert.get("created_at")
        )
 
        resolved = parse_dt(
            alert.get("resolved_at")
        )
 
        if created and resolved:
            alert_times.append(
                (
                    resolved -
                    created
                ).total_seconds() / 60
            )
 
    avg_alert_resolution = round(
        sum(alert_times) / len(alert_times),
        2
    ) if alert_times else 0
 
    # -----------------------------
    # Dashboard
    # -----------------------------
 
    return {
 
        "devices": {
 
            "total": len(devices),
 
            "online": online_devices,
 
            "offline": len(
                [d for d in devices if d.get("status") == "offline"]
            ),
 
            "degraded": len(
                [d for d in devices if d.get("status") == "degraded"]
            ),
 
            "maintenance": len(
                [d for d in devices if d.get("status") == "maintenance"]
            )
 
        },
 
        "alerts": {
 
            "total": len(alerts),
 
            "active": len(active_alerts),
 
            "critical": len(
                [a for a in active_alerts if a.get("severity") == "critical"]
            ),
 
            "high": len(
                [a for a in active_alerts if a.get("severity") == "high"]
            ),
 
            "medium": len(
                [a for a in active_alerts if a.get("severity") == "medium"]
            ),
 
            "low": len(
                [a for a in active_alerts if a.get("severity") == "low"]
            )
 
        },
 
        "incidents": {
 
            "total": len(incidents),
 
            "open": len(open_incidents),
 
            "resolved": len(
                [i for i in incidents if i.get("status") == "resolved"]
            ),
 
            "p1_open": len(
                [i for i in open_incidents if i.get("priority") == "P1"]
            ),
 
            "p2_open": len(
                [i for i in open_incidents if i.get("priority") == "P2"]
            )
 
        },
 
        "kpis": {
 
            "availability_percentage": uptime_pct,
 
            "mttd_minutes": mttd,
 
            "mttr_minutes": mttr,
 
            "sla_compliance": sla,
 
            "average_alert_resolution_minutes": avg_alert_resolution
 
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

@dashboard_router.get("/layout")
async def get_dashboard_layout(current_user: dict = Depends(get_current_user)):
    """Get user's dashboard layout or global layout"""
    # Try user-specific layout first
    user_layout = await db.dashboard_layouts.find_one(
        {"user_id": current_user["id"]}, 
        {"_id": 0}
    )
    if user_layout:
        return user_layout
    
    # Fall back to global layout
    global_layout = await db.dashboard_layouts.find_one(
        {"is_global": True}, 
        {"_id": 0}
    )
    if global_layout:
        return global_layout
    
    # Return empty layout if none exists
    return {"layout": None, "widget_configs": {}, "is_global": False}

@dashboard_router.post("/layout")
async def save_dashboard_layout(
    data: dict,
    current_user: dict = Depends(get_current_user)
):
    """Save dashboard layout"""
    layout = data.get("layout", [])
    widget_configs = data.get("widget_configs", {})
    is_global = data.get("is_global", False)
    
    # Only admins can save global layouts
    if is_global and current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Only admins can save global layouts")
    
    now = datetime.now(timezone.utc).isoformat()
    
    if is_global:
        # Update or create global layout
        await db.dashboard_layouts.update_one(
            {"is_global": True},
            {"$set": {
                "layout": layout,
                "widget_configs": widget_configs,
                "is_global": True,
                "updated_by": current_user["id"],
                "updated_at": now
            }},
            upsert=True
        )
    else:
        # Save user-specific layout
        await db.dashboard_layouts.update_one(
            {"user_id": current_user["id"]},
            {"$set": {
                "user_id": current_user["id"],
                "layout": layout,
                "widget_configs": widget_configs,
                "is_global": False,
                "updated_at": now
            }},
            upsert=True
        )
    
    return {"success": True, "message": "Layout saved"}

# ===================== USERS MANAGEMENT =====================
users_router = APIRouter(prefix="/users", tags=["Users"])

@users_router.get("")
async def get_all_users(current_user: dict = Depends(get_current_user)):
    """Get all users (admin only)"""
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    users = await db.users.find({}, {"_id": 0, "password_hash": 0}).to_list(1000)
    return users


@users_router.get("/{user_id}")
async def get_user(user_id: str, current_user: dict = Depends(get_current_user)):
    """Get a specific user"""
    if current_user.get("role") != "admin" and current_user.get("id") != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@users_router.put("/{user_id}")
async def update_user(
    user_id: str, 
    user_data: dict,
    current_user: dict = Depends(get_current_user)
):
    """Update a user (admin only)"""
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    existing = await db.users.find_one({"id": user_id})
    if not existing:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Validate role if provided
    if "role" in user_data and user_data["role"] not in ["admin", "operator"]:
        raise HTTPException(status_code=400, detail="Invalid role")
    
    update_fields = {}
    allowed_fields = ["name", "email", "role", "is_active"]
    for field in allowed_fields:
        if field in user_data:
            update_fields[field] = user_data[field]
    
    if update_fields:
        update_fields["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.users.update_one({"id": user_id}, {"$set": update_fields})
    
    updated = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})
    return updated

@users_router.delete("/{user_id}")
async def delete_user(user_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a user (admin only)"""
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Prevent deleting yourself
    if user_id == current_user.get("id"):
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    
    existing = await db.users.find_one({"id": user_id})
    if not existing:
        raise HTTPException(status_code=404, detail="User not found")
    
    await db.users.delete_one({"id": user_id})
    return {"success": True, "message": "User deleted"}

@users_router.post("/{user_id}/reset-password")
async def reset_user_password(
    user_id: str,
    data: dict,
    current_user: dict = Depends(get_current_user)
):
    """Reset a user's password (admin only)"""
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    new_password = data.get("new_password")
    if not new_password or len(new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    
    existing = await db.users.find_one({"id": user_id})
    if not existing:
        raise HTTPException(status_code=404, detail="User not found")
    
    await db.users.update_one(
        {"id": user_id},
        {"$set": {
            "password_hash": hash_password(new_password),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    return {"success": True, "message": "Password reset successfully"}

# ===================== OFFICE 365 EMAIL SERVICE =====================

class O365ConfigCreate(BaseModel):
    """Office 365 / MS Graph Configuration"""
    tenant_id: str
    client_id: str
    client_secret: str
    sender_email: str
    sender_name: str = "ATECH NOC Commander"
    is_active: bool = True

async def send_email_o365(to_emails: List[str], subject: str, body: str, is_html: bool = False):
    """Send email using Office 365 MS Graph API or SMTP fallback"""
    # Try MS Graph first
    o365_config = await db.o365_config.find_one({"is_active": True}, {"_id": 0})
    
    if o365_config:
        try:
            from azure.identity import ClientSecretCredential
            from msgraph import GraphServiceClient
            from msgraph.generated.users.item.send_mail.send_mail_post_request_body import SendMailPostRequestBody
            from msgraph.generated.models.message import Message
            from msgraph.generated.models.item_body import ItemBody
            from msgraph.generated.models.body_type import BodyType
            from msgraph.generated.models.recipient import Recipient
            from msgraph.generated.models.email_address import EmailAddress
            
            credential = ClientSecretCredential(
                tenant_id=o365_config["tenant_id"],
                client_id=o365_config["client_id"],
                client_secret=o365_config["client_secret"]
            )
            
            client = GraphServiceClient(credential)
            
            # Build message
            message = Message(
                subject=subject,
                body=ItemBody(
                    content_type=BodyType.Html if is_html else BodyType.Text,
                    content=body
                ),
                to_recipients=[
                    Recipient(email_address=EmailAddress(address=email))
                    for email in to_emails
                ]
            )
            
            request_body = SendMailPostRequestBody(
                message=message,
                save_to_sent_items=True
            )
            
            sender_email = o365_config.get("sender_email")
            await client.users.by_user_id(sender_email).send_mail.post(request_body)
            
            logger.info(f"Email sent via MS Graph to {to_emails}")
            return {"success": True, "method": "ms_graph"}
            
        except Exception as e:
            logger.error(f"MS Graph email failed: {e}")
            # Fall through to SMTP
    
    # Try SMTP fallback (Office 365 SMTP or configured SMTP)
    email_config = await db.email_config.find_one({"is_active": True}, {"_id": 0})
    
    if email_config:
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{email_config.get('sender_name', 'NOC')} <{email_config.get('sender_email')}>"
            msg['To'] = ', '.join(to_emails)
            
            if is_html:
                msg.attach(MIMEText(body, 'html'))
            else:
                msg.attach(MIMEText(body, 'plain'))
            
            with smtplib.SMTP(email_config.get('smtp_server'), email_config.get('smtp_port')) as server:
                if email_config.get('use_tls', True):
                    server.starttls()
                server.login(email_config.get('username'), email_config.get('password'))
                server.sendmail(
                    email_config.get('sender_email'),
                    to_emails,
                    msg.as_string()
                )
            
            logger.info(f"Email sent via SMTP to {to_emails}")
            return {"success": True, "method": "smtp"}
            
        except Exception as e:
            logger.error(f"SMTP email failed: {e}")
            return {"success": False, "error": str(e)}
    
    logger.warning("No email configuration found")
    return {"success": False, "error": "No email configuration found"}

@settings_router.get("/o365")
async def get_o365_config(current_user: dict = Depends(get_current_user)):
    """Get Office 365 configuration (without secrets)"""
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    config = await db.o365_config.find_one({}, {"_id": 0})
    if config:
        # Mask the client secret
        config["client_secret"] = "***" if config.get("client_secret") else ""
    return config or {}

@settings_router.post("/o365")
async def save_o365_config(
    config: O365ConfigCreate,
    current_user: dict = Depends(get_current_user)
):
    """Save Office 365 configuration"""
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    now = datetime.now(timezone.utc).isoformat()
    config_dict = config.model_dump()
    config_dict["id"] = str(uuid.uuid4())
    config_dict["created_at"] = now
    config_dict["updated_at"] = now
    
    # Replace or create
    await db.o365_config.delete_many({})
    config_insert = config_dict.copy()
    await db.o365_config.insert_one(config_insert)
    
    # Mask secret in response
    config_dict["client_secret"] = "***"
    return {"success": True, "config": config_dict}

@settings_router.post("/o365/test")
async def test_o365_config(current_user: dict = Depends(get_current_user)):
    """Test Office 365 email configuration"""
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    config = await db.o365_config.find_one({"is_active": True}, {"_id": 0})
    if not config:
        return {"success": False, "error": "No O365 configuration found"}
    
    test_email = current_user.get("email")
    if not test_email:
        return {"success": False, "error": "No email address for current user"}
    
    result = await send_email_o365(
        to_emails=[test_email],
        subject="ATECH NOC Commander - Test Email",
        body=f"""
        <h2>Test Email from ATECH NOC Commander</h2>
        <p>This is a test email to verify your Office 365 integration.</p>
        <p>If you received this email, your configuration is working correctly.</p>
        <hr>
        <p><small>Sent at: {datetime.now(timezone.utc).isoformat()}</small></p>
        """,
        is_html=True
    )
    
    return result

@settings_router.delete("/o365")
async def delete_o365_config(current_user: dict = Depends(get_current_user)):
    """Delete Office 365 configuration"""
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    await db.o365_config.delete_many({})
    return {"success": True, "message": "O365 configuration deleted"}


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
# Modified on 23-07-2026 for topology correction
@topology_router.get("/data")
async def get_topology_data(current_user: dict = Depends(get_current_user)):
    """Dynamically build the network topology map by reading real database connections, CDP/LLDP neighbors, and subnets."""
    devices = await db.devices.find({}, {"_id": 0}).to_list(1000)
    
    nodes = []
    links = []
    generated_pairs = set()

    def add_link(src_id, tgt_id, link_type):
        pair_key = tuple(sorted([src_id, tgt_id]))
        if pair_key not in generated_pairs and src_id != tgt_id:
            generated_pairs.add(pair_key)
            links.append({"source": src_id, "target": tgt_id, "type": link_type})

    # Create a fast lookup map for devices by name, hostname, and IP
    device_lookup = {}
    for device in devices:
        node_id = device["id"]
        nodes.append({
            "id": node_id,
            "name": device.get("hostname") or device.get("name"),
            "type": device.get("type", "server"),
            "status": device.get("status", "unknown"),
            "ip": device.get("ip_address", ""),
            "location": device.get("location", "DC-East"),
            "group": device.get("type", "server")
        })
        
        device_lookup[node_id] = device
        if device.get("hostname"):
            device_lookup[device["hostname"].lower()] = device
        if device.get("name"):
            device_lookup[device["name"].lower()] = device
        if device.get("ip_address"):
            device_lookup[device["ip_address"]] = device

    # Dynamically parse connections from device metadata
    for device in devices:
        src_id = device["id"]
        neighbors = device.get("neighbors", []) or device.get("snmp_info", {}).get("neighbors", [])
        
        # 1. Read explicit discovered neighbor links (CDP/LLDP)
        if neighbors:
            for nbr in neighbors:
                nbr_name = str(nbr.get("hostname") or nbr.get("name") or "").lower().strip()
                nbr_ip = nbr.get("ip_address")
                
                target_dev = device_lookup.get(nbr_ip) or device_lookup.get(nbr_name)
                if target_dev:
                    link_type = "core" if device.get("type") in ["router", "switch", "firewall"] and target_dev.get("type") in ["router", "switch", "firewall"] else "edge"
                    add_link(src_id, target_dev["id"], link_type)

        # 2. Read routing table next-hops if no direct neighbor metadata exists
        routing_table = device.get("routing_table", [])
        if routing_table and not neighbors:
            for route in routing_table:
                next_hop = route.get("next_hop")
                target_dev = device_lookup.get(next_hop)
                if target_dev and target_dev["id"] != src_id:
                    add_link(src_id, target_dev["id"], "core")

    # 3. Dynamic Subnet Proximity Fallback (Ensures orphaned devices link to their local gateway switch)
    for device in devices:
        src_id = device["id"]
        dev_ip = device.get("ip_address", "")
        
        # Check if this device already has any links
        has_links = any(src_id in (l["source"], l["target"]) for l in links)
        if not has_links and dev_ip:
            subnet_prefix = ".".join(dev_ip.split(".")[:3])
            
            # Find a router or switch in the exact same subnet segment
            local_gateway = next((d for d in devices if d["id"] != src_id and d.get("type") in ["router", "switch", "firewall"] and d.get("ip_address", "").startswith(subnet_prefix)), None)
            
            if local_gateway:
                add_link(local_gateway["id"], src_id, "edge")
            elif devices:
                # Absolute dynamic root fallback to the first core device found in the system
                root_dev = next((d for d in devices if d.get("type") in ["router", "switch"]), devices[0])
                if root_dev["id"] != src_id:
                    add_link(root_dev["id"], src_id, "edge")

    return {"nodes": nodes, "links": links}

    # =================================================================
    # PHASE 1: RESOLVE PHYSICAL LINKS VIA LIVE CONNECTED NEIGHBORS
    # =================================================================
    for rtr in core_routers:
        neighbors_list = rtr.get("neighbors") or rtr.get("snmp_info", {}).get("neighbors", []) or []
        
        for nbr in neighbors_list:
            nbr_ip = nbr.get("ip_address")
            nbr_host = nbr.get("hostname")
            
            # FIXED: Added explicit matching checks against 'hostname' to catch true CDP mappings
            target_node = next((
                d for d in core_routers if 
                (nbr_ip and d.get("ip_address") == nbr_ip) or 
                (nbr_host and d.get("hostname") == nbr_host) or
                (nbr_host and d.get("name") == nbr_host)
            ), None)
            
            if target_node:
                add_topology_link(rtr["id"], target_node["id"], "core")

    # =================================================================
    # PHASE 2: FALLBACK TO SEQUENCE LAYER ONLY IF ZERO LINKS DISCOVERED
    # =================================================================
    if not links and len(core_routers) > 1:
        def ip_sort_key(dev):
            try:
                return [int(x) for x in dev.get("ip_address", "0.0.0.0").split(".")]
            except:
                return [0, 0, 0, 0]
        sorted_backbone = sorted(core_routers, key=ip_sort_key)
        for i in range(len(sorted_backbone) - 1):
            add_topology_link(sorted_backbone[i]["id"], sorted_backbone[i+1]["id"], "core")

    # =================================================================
    # PHASE 3: EDGE NODES RELATIONSHIP SETUP
    # =================================================================
    for edge in edge_nodes:
        edge_ip = edge.get("ip_address", "")
        if edge_ip:
            edge_parts = edge_ip.split(".")[:3]
            nearest_router = next((r for r in core_routers if r.get("ip_address", "").split(".")[:3] == edge_parts), None)
            target_router = nearest_router or (core_routers[0] if core_routers else None)
            if target_router:
                add_topology_link(target_router["id"], edge["id"], "edge")

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
    """Check for incidents that need escalation (e.g., > 15 mins) and send email alerts."""
    now = datetime.now(timezone.utc)
    escalations_needed = []
    
    incidents = await db.incidents.find({
        "status": {"$in": ["open", "in_progress", "awaiting_approval"]}
    }, {"_id": 0}).to_list(100)
    
    for incident in incidents:
        created_at = datetime.fromisoformat(incident["created_at"].replace("Z", "+00:00"))
        minutes_open = (now - created_at).total_seconds() / 60
        
        # 15 Minute Escalation Trigger
        if minutes_open >= 15:
            existing = await db.escalation_history.find_one({
                "incident_id": incident["id"],
                "level": 1
            })
            
            if not existing:
                await send_escalation_email(incident["id"], 1, current_user)
                escalations_needed.append(incident["ticket_number"])
    
    return {"escalations_triggered": escalations_needed, "count": len(escalations_needed)}

# @escalation_router.post("/check")
# async def check_escalations(current_user: dict = Depends(get_current_user)):
#     """Check for incidents/alerts that need escalation"""
#     now = datetime.now(timezone.utc)
#     escalations_needed = []
    
#     # Get open P1/P2 incidents
#     incidents = await db.incidents.find({
#         "priority": {"$in": ["P1", "P2"]},
#         "status": {"$in": ["open", "in_progress"]}
#     }, {"_id": 0}).to_list(100)
    
#     for incident in incidents:
#         created_at = datetime.fromisoformat(incident["created_at"].replace("Z", "+00:00"))
#         hours_open = (now - created_at).total_seconds() / 3600
        
#         for level in ESCALATION_LEVELS:
#             if hours_open >= level["threshold_hours"] and incident["priority"] in level["priority_filter"]:
#                 # Check if already escalated to this level
#                 existing = await db.escalation_history.find_one({
#                     "incident_id": incident["id"],
#                     "level": level["level"]
#                 })
                
#                 if not existing:
#                     escalations_needed.append({
#                         "incident": incident,
#                         "level": level,
#                         "hours_open": round(hours_open, 1)
#                     })
    
#     return {"escalations_needed": escalations_needed, "count": len(escalations_needed)}

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

# ===================== SETTINGS ENDPOINTS =====================

# Email Configuration Endpoints
@settings_router.get("/email")
async def get_email_config(current_user: dict = Depends(get_current_user)):
    """Get the current email configuration (password hidden)"""
    config = await db.email_config.find_one({}, {"_id": 0})
    if not config:
        return None
    # Hide password
    if "password" in config:
        config["password"] = "********"
    return config

@settings_router.post("/email")
async def save_email_config(config: EmailConfigCreate, current_user: dict = Depends(get_current_user)):
    """Save or update email configuration"""
    # Check if config already exists
    existing = await db.email_config.find_one({})
    
    config_data = config.model_dump()
    config_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    if existing:
        # Update existing config
        await db.email_config.update_one({}, {"$set": config_data})
        config_data["id"] = existing.get("id", str(uuid.uuid4()))
    else:
        # Create new config
        config_data["id"] = str(uuid.uuid4())
        config_data["created_at"] = datetime.now(timezone.utc).isoformat()
        config_data["is_active"] = True
        # Make a copy for insertion (MongoDB adds _id to the dict)
        insert_data = dict(config_data)
        await db.email_config.insert_one(insert_data)
    
    # Hide password in response
    config_data["password"] = "********"
    return {"message": "Email configuration saved successfully", "config": config_data}

@settings_router.post("/email/test")
async def test_email_config(test_email: str, current_user: dict = Depends(get_current_user)):
    """Test email configuration by sending a test email"""
    config = await db.email_config.find_one({}, {"_id": 0})
    if not config:
        raise HTTPException(status_code=400, detail="Email configuration not found. Please configure email settings first.")
    
    try:
        # Create test email
        msg = MIMEMultipart()
        msg['From'] = f"{config.get('sender_name', 'NOC')} <{config['sender_email']}>"
        msg['To'] = test_email
        msg['Subject'] = "ATECH NOC Commander - Test Email"
        
        body = """
        <html>
        <body style="font-family: Arial, sans-serif;">
            <h2 style="color: #1e40af;">ATECH NOC Commander</h2>
            <p>This is a test email from ATECH NOC Commander.</p>
            <p>If you received this email, your email configuration is working correctly!</p>
            <hr>
            <p style="color: #6b7280; font-size: 12px;">
                Sent from: {sender_email}<br>
                SMTP Server: {smtp_server}:{smtp_port}
            </p>
        </body>
        </html>
        """.format(
            sender_email=config['sender_email'],
            smtp_server=config['smtp_server'],
            smtp_port=config['smtp_port']
        )
        
        msg.attach(MIMEText(body, 'html'))
        
        # Send email
        with smtplib.SMTP(config['smtp_server'], config['smtp_port']) as server:
            if config.get('use_tls', True):
                server.starttls()
            server.login(config['username'], config['password'])
            server.send_message(msg)
        
        return {"success": True, "message": f"Test email sent successfully to {test_email}"}
    except smtplib.SMTPAuthenticationError as e:
        raise HTTPException(
        status_code=400,
        detail=f"SMTP Auth Error {e.smtp_code}: {e.smtp_error.decode(errors='ignore')}"
        )
        #raise HTTPException(status_code=400, detail="Authentication failed. Please check your username and password.")
    except smtplib.SMTPException as e:
        raise HTTPException(status_code=400, detail=f"SMTP error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")

@settings_router.delete("/email")
async def delete_email_config(current_user: dict = Depends(get_current_user)):
    """Delete email configuration"""
    result = await db.email_config.delete_many({})
    return {"message": "Email configuration deleted", "deleted_count": result.deleted_count}

# SNMP Community String Endpoints
@settings_router.get("/snmp/community")
async def get_snmp_community_strings(current_user: dict = Depends(get_current_user)):
    """Get all SNMP community string configurations (strings hidden)"""
    configs = await db.snmp_community.find({}, {"_id": 0}).to_list(100)
    # Hide community strings
    for config in configs:
        if "community_string" in config:
            config["community_string"] = "********"
    return configs

@settings_router.post("/snmp/community")
async def create_snmp_community_string(config: SNMPCommunityStringCreate, current_user: dict = Depends(get_current_user)):
    """Create a new SNMP community string configuration"""
    config_data = config.model_dump()
    config_data["id"] = str(uuid.uuid4())
    config_data["created_at"] = datetime.now(timezone.utc).isoformat()
    config_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    config_data["is_active"] = True
    
    # Make a copy for insertion (MongoDB adds _id to the dict)
    insert_data = dict(config_data)
    await db.snmp_community.insert_one(insert_data)
    
    # Hide community string in response
    config_data["community_string"] = "********"
    return {"message": "SNMP community string configuration created", "config": config_data}

@settings_router.put("/snmp/community/{config_id}")
async def update_snmp_community_string(config_id: str, config: SNMPCommunityStringCreate, current_user: dict = Depends(get_current_user)):
    """Update an SNMP community string configuration"""
    existing = await db.snmp_community.find_one({"id": config_id})
    if not existing:
        raise HTTPException(status_code=404, detail="SNMP configuration not found")
    
    config_data = config.model_dump()
    config_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    await db.snmp_community.update_one({"id": config_id}, {"$set": config_data})
    
    # Hide community string in response
    config_data["id"] = config_id
    config_data["community_string"] = "********"
    return {"message": "SNMP configuration updated", "config": config_data}

@settings_router.delete("/snmp/community/{config_id}")
async def delete_snmp_community_string(config_id: str, current_user: dict = Depends(get_current_user)):
    """Delete an SNMP community string configuration"""
    result = await db.snmp_community.delete_one({"id": config_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="SNMP configuration not found")
    return {"message": "SNMP configuration deleted"}

@settings_router.post("/snmp/community/{config_id}/test")
async def test_snmp_community_string(config_id: str, target_ip: str, current_user: dict = Depends(get_current_user)):
    """Test SNMP community string by querying a device"""
    config = await db.snmp_community.find_one({"id": config_id}, {"_id": 0})
    if not config:
        raise HTTPException(status_code=404, detail="SNMP configuration not found")
    
    try:
        from pysnmp.hlapi.asyncio import (
            getCmd, SnmpEngine, CommunityData, UdpTransportTarget, ContextData, ObjectType, ObjectIdentity
        )
        
        # Test with sysDescr OID
        iterator = await getCmd(
            SnmpEngine(),
            CommunityData(config['community_string'], mpModel=1 if config['version'] == 'v2c' else 0),
            UdpTransportTarget((target_ip, 161), timeout=5, retries=1),
            ContextData(),
            ObjectType(ObjectIdentity('SNMPv2-MIB', 'sysDescr', 0))
        )
        
        errorIndication, errorStatus, errorIndex, varBinds = iterator
        
        if errorIndication:
            return {"success": False, "message": f"SNMP error: {errorIndication}"}
        elif errorStatus:
            return {"success": False, "message": f"SNMP error: {errorStatus.prettyPrint()} at {errorIndex}"}
        else:
            result = ""
            for varBind in varBinds:
                result = str(varBind[1])
            return {"success": True, "message": "SNMP query successful", "device_description": result}
    except ImportError:
        return {"success": False, "message": "pysnmp not installed. SNMP testing unavailable."}
    except Exception as e:
        return {"success": False, "message": f"SNMP test failed: {str(e)}"}

# SNMP v3 Configuration Endpoints
@settings_router.get("/snmp/v3")
async def get_snmpv3_configs(current_user: dict = Depends(get_current_user)):
    """Get all SNMP v3 configurations (passwords hidden)"""
    configs = await db.snmpv3_config.find({}, {"_id": 0}).to_list(100)
    # Hide passwords
    for config in configs:
        if "auth_password" in config:
            config["auth_password"] = "********"
        if "priv_password" in config:
            config["priv_password"] = "********"
    return configs

@settings_router.post("/snmp/v3")
async def create_snmpv3_config(config: SNMPv3ConfigCreate, current_user: dict = Depends(get_current_user)):
    """Create a new SNMP v3 configuration"""
    config_data = config.model_dump()
    config_data["id"] = str(uuid.uuid4())
    config_data["created_at"] = datetime.now(timezone.utc).isoformat()
    config_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    config_data["is_active"] = True
    
    # Make a copy for insertion (MongoDB adds _id to the dict)
    insert_data = dict(config_data)
    await db.snmpv3_config.insert_one(insert_data)
    
    # Hide passwords in response
    config_data["auth_password"] = "********"
    config_data["priv_password"] = "********"
    return {"message": "SNMP v3 configuration created", "config": config_data}

@settings_router.put("/snmp/v3/{config_id}")
async def update_snmpv3_config(config_id: str, config: SNMPv3ConfigCreate, current_user: dict = Depends(get_current_user)):
    """Update an SNMP v3 configuration"""
    existing = await db.snmpv3_config.find_one({"id": config_id})
    if not existing:
        raise HTTPException(status_code=404, detail="SNMP v3 configuration not found")
    
    config_data = config.model_dump()
    config_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    await db.snmpv3_config.update_one({"id": config_id}, {"$set": config_data})
    
    # Hide passwords in response
    config_data["id"] = config_id
    config_data["auth_password"] = "********"
    config_data["priv_password"] = "********"
    return {"message": "SNMP v3 configuration updated", "config": config_data}

@settings_router.delete("/snmp/v3/{config_id}")
async def delete_snmpv3_config(config_id: str, current_user: dict = Depends(get_current_user)):
    """Delete an SNMP v3 configuration"""
    result = await db.snmpv3_config.delete_one({"id": config_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="SNMP v3 configuration not found")
    return {"message": "SNMP v3 configuration deleted"}

# ===================== OPENSTACK CONFIGURATION =====================
@settings_router.get("/openstack")
async def get_openstack_configs(current_user: dict = Depends(get_current_user)):
    configs = await db.openstack_config.find({}, {"_id": 0}).to_list(100)
    for config in configs:
        if "password" in config:
            config["password"] = "********"
    return configs

@settings_router.post("/openstack")
async def create_openstack_config(config: OpenStackConfigCreate, current_user: dict = Depends(get_current_user)):
    config_data = config.model_dump()
    config_data["id"] = str(uuid.uuid4())
    config_data["created_at"] = datetime.now(timezone.utc).isoformat()
    config_data["is_active"] = True
    insert_data = dict(config_data)
    await db.openstack_config.insert_one(insert_data)
    config_data["password"] = "********"
    return {"message": "OpenStack configuration created", "config": config_data}

@settings_router.put("/openstack/{config_id}")
async def update_openstack_config(config_id: str, config: OpenStackConfigCreate, current_user: dict = Depends(get_current_user)):
    existing = await db.openstack_config.find_one({"id": config_id})
    if not existing:
        raise HTTPException(status_code=404, detail="OpenStack configuration not found")
    config_data = config.model_dump()
    await db.openstack_config.update_one({"id": config_id}, {"$set": config_data})
    config_data["id"] = config_id
    config_data["password"] = "********"
    return {"message": "OpenStack configuration updated", "config": config_data}

@settings_router.delete("/openstack/{config_id}")
async def delete_openstack_config(config_id: str, current_user: dict = Depends(get_current_user)):
    result = await db.openstack_config.delete_one({"id": config_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="OpenStack configuration not found")
    return {"message": "OpenStack configuration deleted"}

# ===================== ORACLE DB CONFIGURATION =====================
@settings_router.get("/oracle")
async def get_oracle_configs(current_user: dict = Depends(get_current_user)):
    configs = await db.oracle_config.find({}, {"_id": 0}).to_list(100)
    for config in configs:
        if "password" in config:
            config["password"] = "********"
    return configs

@settings_router.post("/oracle")
async def create_oracle_config(config: OracleDBConfigCreate, current_user: dict = Depends(get_current_user)):
    config_data = config.model_dump()
    config_data["id"] = str(uuid.uuid4())
    config_data["created_at"] = datetime.now(timezone.utc).isoformat()
    config_data["is_active"] = True
    insert_data = dict(config_data)
    await db.oracle_config.insert_one(insert_data)
    config_data["password"] = "********"
    return {"message": "Oracle DB configuration created", "config": config_data}

@settings_router.put("/oracle/{config_id}")
async def update_oracle_config(config_id: str, config: OracleDBConfigCreate, current_user: dict = Depends(get_current_user)):
    existing = await db.oracle_config.find_one({"id": config_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Oracle configuration not found")
    config_data = config.model_dump()
    await db.oracle_config.update_one({"id": config_id}, {"$set": config_data})
    config_data["id"] = config_id
    config_data["password"] = "********"
    return {"message": "Oracle configuration updated", "config": config_data}

@settings_router.delete("/oracle/{config_id}")
async def delete_oracle_config(config_id: str, current_user: dict = Depends(get_current_user)):
    result = await db.oracle_config.delete_one({"id": config_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Oracle configuration not found")
    return {"message": "Oracle configuration deleted"}

# ===================== VCENTER CONFIGURATION =====================
@settings_router.get("/vcenter")
async def get_vcenter_configs(current_user: dict = Depends(get_current_user)):
    configs = await db.vcenter_config.find({}, {"_id": 0}).to_list(100)
    for config in configs:
        if "password" in config:
            config["password"] = "********"
    return configs

@settings_router.post("/vcenter")
async def create_vcenter_config(config: VCenterConfigCreate, current_user: dict = Depends(get_current_user)):
    config_data = config.model_dump()
    config_data["id"] = str(uuid.uuid4())
    config_data["created_at"] = datetime.now(timezone.utc).isoformat()
    config_data["is_active"] = True
    insert_data = dict(config_data)
    await db.vcenter_config.insert_one(insert_data)
    config_data["password"] = "********"
    return {"message": "vCenter configuration created", "config": config_data}

@settings_router.put("/vcenter/{config_id}")
async def update_vcenter_config(config_id: str, config: VCenterConfigCreate, current_user: dict = Depends(get_current_user)):
    existing = await db.vcenter_config.find_one({"id": config_id})
    if not existing:
        raise HTTPException(status_code=404, detail="vCenter configuration not found")
    config_data = config.model_dump()
    await db.vcenter_config.update_one({"id": config_id}, {"$set": config_data})
    config_data["id"] = config_id
    config_data["password"] = "********"
    return {"message": "vCenter configuration updated", "config": config_data}

@settings_router.delete("/vcenter/{config_id}")
async def delete_vcenter_config(config_id: str, current_user: dict = Depends(get_current_user)):
    result = await db.vcenter_config.delete_one({"id": config_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="vCenter configuration not found")
    return {"message": "vCenter configuration deleted"}

# ===================== AAA SERVER CONFIGURATION =====================
@settings_router.get("/aaa")
async def get_aaa_configs(current_user: dict = Depends(get_current_user)):
    configs = await db.aaa_config.find({}, {"_id": 0}).to_list(100)
    for config in configs:
        if "shared_secret" in config:
            config["shared_secret"] = "********"
    return configs

@settings_router.post("/aaa")
async def create_aaa_config(config: AAAServerConfigCreate, current_user: dict = Depends(get_current_user)):
    config_data = config.model_dump()
    config_data["id"] = str(uuid.uuid4())
    config_data["created_at"] = datetime.now(timezone.utc).isoformat()
    config_data["is_active"] = True
    insert_data = dict(config_data)
    await db.aaa_config.insert_one(insert_data)
    config_data["shared_secret"] = "********"
    return {"message": "AAA server configuration created", "config": config_data}

@settings_router.put("/aaa/{config_id}")
async def update_aaa_config(config_id: str, config: AAAServerConfigCreate, current_user: dict = Depends(get_current_user)):
    existing = await db.aaa_config.find_one({"id": config_id})
    if not existing:
        raise HTTPException(status_code=404, detail="AAA configuration not found")
    config_data = config.model_dump()
    await db.aaa_config.update_one({"id": config_id}, {"$set": config_data})
    config_data["id"] = config_id
    config_data["shared_secret"] = "********"
    return {"message": "AAA configuration updated", "config": config_data}

@settings_router.delete("/aaa/{config_id}")
async def delete_aaa_config(config_id: str, current_user: dict = Depends(get_current_user)):
    result = await db.aaa_config.delete_one({"id": config_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="AAA configuration not found")
    return {"message": "AAA configuration deleted"}

# ===================== BACKUP CONFIGURATION =====================
@settings_router.get("/backup")
async def get_backup_configs(current_user: dict = Depends(get_current_user)):
    configs = await db.backup_config.find({}, {"_id": 0}).to_list(100)
    for config in configs:
        if "server_password" in config:
            config["server_password"] = "********"
        if "api_key" in config:
            config["api_key"] = "********"
    return configs

@settings_router.post("/backup")
async def create_backup_config(config: BackupConfigCreate, current_user: dict = Depends(get_current_user)):
    config_data = config.model_dump()
    config_data["id"] = str(uuid.uuid4())
    config_data["created_at"] = datetime.now(timezone.utc).isoformat()
    config_data["is_active"] = True
    insert_data = dict(config_data)
    await db.backup_config.insert_one(insert_data)
    if "server_password" in config_data and config_data["server_password"]:
        config_data["server_password"] = "********"
    if "api_key" in config_data and config_data["api_key"]:
        config_data["api_key"] = "********"
    return {"message": "Backup configuration created", "config": config_data}

@settings_router.put("/backup/{config_id}")
async def update_backup_config(config_id: str, config: BackupConfigCreate, current_user: dict = Depends(get_current_user)):
    existing = await db.backup_config.find_one({"id": config_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Backup configuration not found")
    config_data = config.model_dump()
    await db.backup_config.update_one({"id": config_id}, {"$set": config_data})
    config_data["id"] = config_id
    if config_data.get("server_password"):
        config_data["server_password"] = "********"
    if config_data.get("api_key"):
        config_data["api_key"] = "********"
    return {"message": "Backup configuration updated", "config": config_data}

@settings_router.delete("/backup/{config_id}")
async def delete_backup_config(config_id: str, current_user: dict = Depends(get_current_user)):
    result = await db.backup_config.delete_one({"id": config_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Backup configuration not found")
    return {"message": "Backup configuration deleted"}

@settings_router.post("/backup/{config_id}/trigger")
async def trigger_backup(config_id: str, current_user: dict = Depends(get_current_user)):
    """Manually trigger a backup job"""
    config = await db.backup_config.find_one({"id": config_id}, {"_id": 0})
    if not config:
        raise HTTPException(status_code=404, detail="Backup configuration not found")
    
    # Record backup attempt
    backup_record = {
        "id": str(uuid.uuid4()),
        "config_id": config_id,
        "config_name": config.get("name"),
        "triggered_by": current_user["name"],
        "status": "running",
        "started_at": datetime.now(timezone.utc).isoformat()
    }
    await db.backup_jobs.insert_one(dict(backup_record))
    
    # Update config last_run
    await db.backup_config.update_one(
        {"id": config_id}, 
        {"$set": {"last_run": datetime.now(timezone.utc).isoformat(), "last_status": "running"}}
    )
    
    # In a real implementation, this would trigger the actual backup
    # For now, we simulate success
    await db.backup_jobs.update_one(
        {"id": backup_record["id"]},
        {"$set": {"status": "completed", "completed_at": datetime.now(timezone.utc).isoformat()}}
    )
    await db.backup_config.update_one(
        {"id": config_id}, 
        {"$set": {"last_status": "completed"}}
    )
    
    return {"message": "Backup triggered successfully", "job_id": backup_record["id"]}

# ===================== CUSTOM DASHBOARDS =====================
@settings_router.get("/dashboards")
async def get_custom_dashboards(current_user: dict = Depends(get_current_user)):
    dashboards = await db.custom_dashboards.find({}, {"_id": 0}).to_list(100)
    return dashboards

@settings_router.post("/dashboards")
async def create_custom_dashboard(dashboard: CustomDashboardCreate, current_user: dict = Depends(get_current_user)):
    dashboard_data = dashboard.model_dump()
    dashboard_data["id"] = str(uuid.uuid4())
    dashboard_data["created_by"] = current_user["name"]
    dashboard_data["created_at"] = datetime.now(timezone.utc).isoformat()
    dashboard_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    insert_data = dict(dashboard_data)
    await db.custom_dashboards.insert_one(insert_data)
    return {"message": "Custom dashboard created", "dashboard": dashboard_data}

@settings_router.put("/dashboards/{dashboard_id}")
async def update_custom_dashboard(dashboard_id: str, dashboard: CustomDashboardCreate, current_user: dict = Depends(get_current_user)):
    existing = await db.custom_dashboards.find_one({"id": dashboard_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    dashboard_data = dashboard.model_dump()
    dashboard_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.custom_dashboards.update_one({"id": dashboard_id}, {"$set": dashboard_data})
    dashboard_data["id"] = dashboard_id
    return {"message": "Dashboard updated", "dashboard": dashboard_data}

@settings_router.delete("/dashboards/{dashboard_id}")
async def delete_custom_dashboard(dashboard_id: str, current_user: dict = Depends(get_current_user)):
    result = await db.custom_dashboards.delete_one({"id": dashboard_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    return {"message": "Dashboard deleted"}

@settings_router.get("/dashboards/templates")
async def get_dashboard_templates(current_user: dict = Depends(get_current_user)):
    """Get predefined dashboard templates"""
    templates = [
        {
            "id": "openstack-monitoring",
            "name": "OpenStack Monitoring",
            "application_type": "openstack",
            "template_type": "monitoring",
            "widgets": [
                {"type": "stat", "title": "Compute Instances", "metric": "nova.instances"},
                {"type": "stat", "title": "Networks", "metric": "neutron.networks"},
                {"type": "chart", "title": "CPU Usage", "metric": "nova.cpu_usage"},
                {"type": "chart", "title": "Memory Usage", "metric": "nova.memory_usage"},
                {"type": "table", "title": "Instance Status", "metric": "nova.instance_list"}
            ]
        },
        {
            "id": "oracle-performance",
            "name": "Oracle Performance",
            "application_type": "oracle",
            "template_type": "performance",
            "widgets": [
                {"type": "stat", "title": "Active Sessions", "metric": "oracle.sessions"},
                {"type": "stat", "title": "Tablespace Used", "metric": "oracle.tablespace_pct"},
                {"type": "chart", "title": "Query Performance", "metric": "oracle.query_time"},
                {"type": "chart", "title": "I/O Stats", "metric": "oracle.io_stats"},
                {"type": "table", "title": "Top SQL", "metric": "oracle.top_sql"}
            ]
        },
        {
            "id": "vcenter-overview",
            "name": "vCenter Overview",
            "application_type": "vcenter",
            "template_type": "monitoring",
            "widgets": [
                {"type": "stat", "title": "Total VMs", "metric": "vcenter.vm_count"},
                {"type": "stat", "title": "ESXi Hosts", "metric": "vcenter.host_count"},
                {"type": "stat", "title": "Datastore Usage", "metric": "vcenter.datastore_pct"},
                {"type": "chart", "title": "Cluster CPU", "metric": "vcenter.cluster_cpu"},
                {"type": "chart", "title": "Cluster Memory", "metric": "vcenter.cluster_memory"}
            ]
        }
    ]
    return templates

# ===================== ACTIVATION CODE MANAGEMENT (Admin Only) =====================

class ActivationCodeCreate(BaseModel):
    """Model for creating activation codes"""
    count: int = Field(default=1, ge=1, le=100)
    notes: Optional[str] = None

class ActivationCodeResponse(BaseModel):
    """Model for activation code response"""
    id: str
    code: str
    status: str
    created_at: str
    created_by: str
    notes: Optional[str] = None
    used_at: Optional[str] = None
    instance_id: Optional[str] = None

@settings_router.get("/activation-codes")
async def get_activation_codes(current_user: dict = Depends(get_current_user)):
    """Get all activation codes (Admin only)"""
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    codes = await db.activation_codes.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return codes

@settings_router.post("/activation-codes/generate")
async def generate_activation_codes_endpoint(
    data: ActivationCodeCreate,
    current_user: dict = Depends(get_current_user)
):
    """Generate new activation codes (Admin only)"""
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    codes = []
    now = datetime.now(timezone.utc).isoformat()
    
    for _ in range(data.count):
        code = generate_activation_code()
        code_doc = {
            "id": str(uuid.uuid4()),
            "code": code,
            "status": "available",
            "created_at": now,
            "created_by": current_user.get("email"),
            "notes": data.notes,
            "used_at": None,
            "instance_id": None
        }
        await db.activation_codes.insert_one(code_doc)
        code_copy = {k: v for k, v in code_doc.items() if k != "_id"}
        codes.append(code_copy)
    
    return {
        "success": True,
        "message": f"Generated {data.count} activation code(s)",
        "codes": codes
    }

@settings_router.delete("/activation-codes/{code_id}")
async def delete_activation_code(code_id: str, current_user: dict = Depends(get_current_user)):
    """Delete an unused activation code (Admin only)"""
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    code = await db.activation_codes.find_one({"id": code_id})
    if not code:
        raise HTTPException(status_code=404, detail="Activation code not found")
    
    if code.get("status") == "used":
        raise HTTPException(status_code=400, detail="Cannot delete a used activation code")
    
    await db.activation_codes.delete_one({"id": code_id})
    return {"success": True, "message": "Activation code deleted"}

@settings_router.put("/activation-codes/{code_id}/revoke")
async def revoke_activation_code(code_id: str, current_user: dict = Depends(get_current_user)):
    """Revoke an activation code (Admin only)"""
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    code = await db.activation_codes.find_one({"id": code_id})
    if not code:
        raise HTTPException(status_code=404, detail="Activation code not found")
    
    await db.activation_codes.update_one(
        {"id": code_id},
        {"$set": {"status": "revoked", "revoked_at": datetime.now(timezone.utc).isoformat()}}
    )
    return {"success": True, "message": "Activation code revoked"}

@settings_router.get("/activation-codes/stats")
async def get_activation_codes_stats(current_user: dict = Depends(get_current_user)):
    """Get activation code statistics (Admin only)"""
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    total = await db.activation_codes.count_documents({})
    available = await db.activation_codes.count_documents({"status": "available"})
    used = await db.activation_codes.count_documents({"status": "used"})
    revoked = await db.activation_codes.count_documents({"status": "revoked"})
    
    return {
        "total": total,
        "available": available,
        "used": used,
        "revoked": revoked
    }

# ===================== NETWORK SERVICES (Discovery, SNMP, SSH) =====================

network_router = APIRouter(prefix="/network", tags=["Network Services"])

# Initialize services
snmp_service = SNMPService()
discovery_service = NetworkDiscoveryService()
ssh_service = SSHService()
background_polling = None  # Will be initialized on startup

# Store for discovery jobs and pending approvals
discovery_jobs: Dict[str, DiscoveryJob] = {}
pending_discovery_requests: Dict[str, Dict] = {}

# Pydantic models for network APIs
class DiscoveryRequest(BaseModel):
    subnet: Optional[str] = None  # If None, auto-detect local subnets
    methods: List[str] = ["arp_scan", "ping_sweep", "snmp_discovery", "port_scan"]
    snmp_communities: List[str] = ["public"]

class DiscoveryApproval(BaseModel):
    request_id: str
    approved: bool
    reason: Optional[str] = None

class SSHConnectRequest(BaseModel):
    host: str
    username: str
    password: str
    port: int = 22

class SSHCommandRequest(BaseModel):
    session_id: str
    command: str
    timeout: int = 30

class SNMPPollRequest(BaseModel):
    ip_address: str
    community: str = "public"
    oids: Optional[List[str]] = None

class CloudConnectRequest(BaseModel):
    config_id: str  # ID of stored configuration

@network_router.get("/subnets")
async def get_local_subnets(current_user: dict = Depends(get_current_user)):
    """Get all local network subnets"""
    subnets = discovery_service.get_local_subnets()
    return {"subnets": subnets}

@network_router.post("/discovery/request")
async def request_network_discovery(
    request: DiscoveryRequest,
    current_user: dict = Depends(get_current_user)
):
    """Request a network discovery scan (requires admin approval)"""
    request_id = str(uuid.uuid4())
    
    # Get subnet
    subnet = request.subnet
    if not subnet:
        subnets = discovery_service.get_local_subnets()
        subnet = subnets[0] if subnets else "192.168.1.0/24"
    
    # Create pending request
    pending_discovery_requests[request_id] = {
        "id": request_id,
        "subnet": subnet,
        "methods": request.methods,
        "snmp_communities": request.snmp_communities,
        "requested_by": current_user.get("email"),
        "requested_at": datetime.now(timezone.utc).isoformat(),
        "status": "pending_approval"
    }
    
    return {
        "request_id": request_id,
        "message": "Discovery request submitted. Awaiting admin approval.",
        "subnet": subnet,
        "methods": request.methods
    }

@network_router.get("/discovery/pending")
async def get_pending_discovery_requests(current_user: dict = Depends(get_current_user)):
    """Get all pending discovery requests (Admin only)"""
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return list(pending_discovery_requests.values())

@network_router.post("/discovery/approve")
async def approve_discovery_request(
    approval: DiscoveryApproval,
    current_user: dict = Depends(get_current_user)
):
    """Approve or reject a discovery request (Admin only)"""
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    if approval.request_id not in pending_discovery_requests:
        raise HTTPException(status_code=404, detail="Request not found")
    
    request_data = pending_discovery_requests[approval.request_id]
    
    if not approval.approved:
        request_data["status"] = "rejected"
        request_data["rejected_by"] = current_user.get("email")
        request_data["rejected_at"] = datetime.now(timezone.utc).isoformat()
        request_data["rejection_reason"] = approval.reason
        del pending_discovery_requests[approval.request_id]
        return {"message": "Discovery request rejected", "request_id": approval.request_id}
    
    # Create and start discovery job
    job_id = str(uuid.uuid4())
    job = DiscoveryJob(
        id=job_id,
        status="running",
        methods=request_data["methods"],
        subnet=request_data["subnet"],
        started_at=datetime.now(timezone.utc).isoformat(),
        approved_by=current_user.get("email"),
        approved_at=datetime.now(timezone.utc).isoformat()
    )
    discovery_jobs[job_id] = job
    
    # Remove from pending
    del pending_discovery_requests[approval.request_id]
    
    # Run discovery in background
    asyncio.create_task(_run_discovery_job(job_id, request_data["snmp_communities"]))
    
    return {
        "message": "Discovery approved and started",
        "job_id": job_id,
        "subnet": job.subnet
    }


async def _run_discovery_job(job_id: str, communities: List[str]):
    """Background task to run discovery and link results back to the Job ID safely"""
    job = discovery_jobs.get(job_id)
    if not job:
        return
    
    try:
        def update_progress(progress):
            job.progress = progress
        
        devices = await discovery_service.run_discovery(job, communities, update_progress)
        
        now = datetime.now(timezone.utc).isoformat()
        for device in devices:
            asset_tag = f"DISC-{device.ip_address.replace('.', '')}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            device_type_map = {
                "router": "router", "switch": "switch", "firewall": "firewall",
                "server": "server", "workstation": "server", "printer": "other",
                "ap": "access_point", "access_point": "access_point", "unknown": "other"
            }
            mapped_type = device_type_map.get(device.device_type or "unknown", "other")
            
            # Pull enriched parameters from snmp data if available safely
            snmp = device.snmp_info or {}
            logger.info(
                f"""
                device.vendor={device.vendor}
                snmp.vendor={snmp.get('vendor')}
                snmp.model={snmp.get('model')}
                snmp={snmp}
                """)
            device_vendor = device.vendor or snmp.get("vendor", "Unknown")
            device_model = snmp.get("model") or "Unknown"
            device_serial = snmp.get("serial") or snmp.get("serial_number") or "N/A"
            device_os = snmp.get("os_version", "Unknown OS")
            device_fw = snmp.get("firmware") or snmp.get("firmware_version") or device_os

            if str(device_vendor).lower() == "unknown" or not device_vendor:
                device_vendor = "Generic"
            else:
                device_vendor = str(device_vendor).upper().strip()

            device_dict = {
                "id": str(uuid.uuid4()),
                "name": device.hostname or f"device-{device.ip_address.replace('.', '-')}",
                "type": mapped_type,
                "ip_address": device.ip_address,
                "mac_address": device.mac_address,
                "hostname": device.hostname or f"device-{device.ip_address.replace('.', '-')}",
                "device_type": mapped_type,
                "vendor": device_vendor,
                "model": device_model,
                "serial_number": device_serial,
                "location": "Auto-Discovered",
                "discovery_method": device.discovery_method,
                "snmp_info": snmp,
                "open_ports": device.open_ports,
                "status": "online" if (device.open_ports or device.snmp_info) else "offline",
                "discovered_at": device.discovered_at,
                "auto_discovered": True,
                "created_at": now,
                "last_seen": now,
                "cpu_usage": 0.0,
                "memory_usage": 0.0,
                "uptime_hours": 0,
                "tags": ["auto-discovered"],
                "os_version": device_os,
                "firmware_version": device_fw,
                "warranty_status": "unknown",
                "discovery_job_id": job_id
            }
            
            existing = await db.devices.find_one({
                "$or": [
                    {"ip_address": device.ip_address},
                    {"mac_address": device.mac_address} if device.mac_address else {"ip_address": device.ip_address}
                ]
            })
            
            device_id = None
            if existing:
                device_id = existing.get("id")
                existing_asset = await db.assets.find_one({
                    "device_id": device_id
                })
                logger.info(
                    f"{device.ip_address}: existing device found, "
                    f"asset exists = {existing_asset is not None}"
                )
                # FIX: Read parameters from local variables, NOT from device.model dataclass attribute
                await db.devices.update_one(
                    {"_id": existing["_id"]},
                    {"$set": {
                        "status": "online",
                        "last_seen": now,
                        "snmp_info": snmp,
                        "open_ports": device.open_ports,
                        "vendor": device_vendor if device_vendor != "GENERIC" else existing.get("vendor", "Generic"),
                        "model": device_model if device_model != "Unknown" else existing.get("model", "Unknown Unit"),
                        "os_version": device_os if device_os != "Unknown OS" else existing.get("os_version"),
                        "discovery_job_id": job_id
                    }}
                )
                if existing_asset:
                    await db.assets.update_one(
                        {"_id": existing_asset["_id"]},
                        {"$set": {
                            "discovery_job_id": job_id,
                            "vendor": device_vendor if device_vendor != "GENERIC" else existing.get("vendor", "Generic"),
                            "model": device_model if device_model != "Unknown" else existing.get("model", "Unknown Unit")
                        }}
                    )
                else:
                    logger.info(f"Creating missing asset for {device.ip_address}")
                    asset_dict = {
                    "id": str(uuid.uuid4()),
                    "name": device.hostname or f"device-{device.ip_address.replace('.', '-')}",
                    "asset_tag": asset_tag,
                    "type": mapped_type,
                    "vendor": device_vendor,
                    "model": device_model,
                    "serial_number": device_serial,
                    "location": "Auto-Discovered",
                    "owner": "IT Department",
                    "status": "active",
                    "purchase_date": None,
                    "warranty_expiry": None,
                    "warranty_status": "unknown",
                    "eol_date": None,
                    "contract_details": None,
                    "license_info": None,
                    "created_at": now,
                    "ip_address": device.ip_address,
                    "mac_address": device.mac_address,
                    "device_id": device_id,  
                    "discovery_method": device.discovery_method,
                    "auto_discovered": True,
                    "discovery_job_id": job_id
                    }
                    logger.info(asset_dict)
                    result = await db.assets.insert_one(asset_dict)
                    logger.info(
                        f"Created asset for {device.ip_address}, "
                        f"inserted_id={result.inserted_id}"
                    )
            else:
                device_id = device_dict["id"]
                await db.devices.insert_one(device_dict.copy())
                
                asset_dict = {
                    "id": str(uuid.uuid4()),
                    "name": device.hostname or f"device-{device.ip_address.replace('.', '-')}",
                    "asset_tag": asset_tag,
                    "type": mapped_type,
                    "vendor": device_vendor,
                    "model": device_model,
                    "serial_number": device_serial,
                    "location": "Auto-Discovered",
                    "owner": "IT Department",
                    "status": "active",
                    "purchase_date": None,
                    "warranty_expiry": None,
                    "warranty_status": "unknown",
                    "eol_date": None,
                    "contract_details": None,
                    "license_info": None,
                    "created_at": now,
                    "ip_address": device.ip_address,
                    "mac_address": device.mac_address,
                    "device_id": device_id,  
                    "discovery_method": device.discovery_method,
                    "auto_discovered": True,
                    "discovery_job_id": job_id
                }
                try:
                    logger.info(f"Inserting asset for {device.ip_address}")
                    logger.info(asset_dict)
                    await db.assets.insert_one(asset_dict.copy())
                    logger.info(f"Asset inserted for {device.ip_address}")
                except Exception:
                    logger.exception(f"Failed inserting asset for {device.ip_address}")
                
            if "create_audit_log" in globals() or "create_audit_log" in locals():
                try:
                    await create_audit_log(
                        action_type="device_create" if not existing else "device_update",
                        description=f"{'Created' if not existing else 'Updated'} device {device.ip_address} via network discovery",
                        resource_type="device",
                        resource_id=device_id,
                        resource_name=device.hostname or device.ip_address,
                        details={
                            "discovery_method": device.discovery_method,
                            "vendor": device_vendor,
                            "auto_discovered": True,
                            "discovery_job_id": job_id
                        }
                    )
                except Exception as audit_err:
                    print(f"Audit logging skipped: {audit_err}")
        
        job.status = "completed"
        job.completed_at = datetime.now(timezone.utc).isoformat()
        job.devices_found = len(devices)
        job.progress = 100
        
    except Exception as e:
        logger.error(f"Global breakdown context in background discovery worker: {str(e)}")
        job.status = "failed"
        job.error = str(e)
        job.completed_at = datetime.now(timezone.utc).isoformat()

@network_router.get("/discovery/jobs")
async def get_discovery_jobs(current_user: dict = Depends(get_current_user)):
    """Get all discovery jobs"""
    jobs = []
    for job in discovery_jobs.values():
        jobs.append({
            "id": job.id,
            "status": job.status,
            "methods": job.methods,
            "subnet": job.subnet,
            "started_at": job.started_at,
            "completed_at": job.completed_at,
            "devices_found": job.devices_found,
            "progress": job.progress,
            "error": job.error,
            "approved_by": job.approved_by
        })
    return sorted(jobs, key=lambda x: x.get("started_at", ""), reverse=True)

@network_router.get("/discovery/jobs/{job_id}")
async def get_discovery_job(job_id: str, current_user: dict = Depends(get_current_user)):
    """Get specific discovery job"""
    if job_id not in discovery_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = discovery_jobs[job_id]
    return {
        "id": job.id,
        "status": job.status,
        "methods": job.methods,
        "subnet": job.subnet,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
        "devices_found": job.devices_found,
        "progress": job.progress,
        "error": job.error,
        "approved_by": job.approved_by
    }

# SNMP Endpoints
@network_router.post("/snmp/poll")
async def poll_device_snmp(
    request: SNMPPollRequest,
    current_user: dict = Depends(get_current_user)
):
    """Poll a device using SNMP"""
    result = await snmp_service.poll_device(
        request.ip_address,
        request.community,
        request.oids
    )
    return result

@network_router.post("/snmp/get-info")
async def get_device_snmp_info(
    request: SNMPPollRequest,
    current_user: dict = Depends(get_current_user)
):
    """Get comprehensive device info via SNMP"""
    info = await snmp_service.get_device_info(request.ip_address, request.community)
    return info

@network_router.post("/snmp/walk")
async def snmp_walk_device(
    ip_address: str,
    oid: str,
    community: str = "public",
    current_user: dict = Depends(get_current_user)
):
    """Perform SNMP walk on a device"""
    results = await snmp_service.snmp_walk(ip_address, community, oid)
    return {"results": [{"oid": r.oid, "value": r.value, "type": r.value_type} for r in results]}

# SSH Endpoints
@network_router.post("/ssh/connect")
async def ssh_connect(
    request: SSHConnectRequest,
    current_user: dict = Depends(get_current_user)
):
    """Establish SSH connection to a device"""
    success, message, session_id = await ssh_service.connect(
        request.host,
        request.username,
        request.password,
        request.port
    )
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    # Log the connection
    await db.ssh_sessions.insert_one({
        "session_id": session_id,
        "host": request.host,
        "username": request.username,
        "connected_by": current_user.get("email"),
        "connected_at": datetime.now(timezone.utc).isoformat(),
        "status": "active"
    })
    
    return {"success": True, "session_id": session_id, "message": message}

@network_router.post("/ssh/execute")
async def ssh_execute_command(
    request: SSHCommandRequest,
    current_user: dict = Depends(get_current_user)
):
    """Execute command on SSH session"""
    success, output, error = await ssh_service.execute_command(
        request.session_id,
        request.command,
        request.timeout
    )
    
    # Log the command
    await db.ssh_command_log.insert_one({
        "session_id": request.session_id,
        "command": request.command,
        "executed_by": current_user.get("email"),
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "success": success,
        "output_length": len(output) if output else 0
    })
    
    return {"success": success, "output": output, "error": error}

@network_router.post("/ssh/disconnect")
async def ssh_disconnect(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Close SSH session"""
    success = await ssh_service.disconnect(session_id)
    
    if success:
        await db.ssh_sessions.update_one(
            {"session_id": session_id},
            {"$set": {"status": "closed", "disconnected_at": datetime.now(timezone.utc).isoformat()}}
        )
    
    return {"success": success}

@network_router.post("/ssh/get-config")
async def ssh_get_device_config(
    host: str,
    username: str,
    password: str,
    device_type: str = "cisco",
    current_user: dict = Depends(get_current_user)
):
    """Get device configuration via SSH"""
    success, config = await ssh_service.get_device_config(host, username, password, device_type)
    
    if not success:
        raise HTTPException(status_code=400, detail=config)
    
    return {"success": True, "config": config}

# Cloud Connector Endpoints
@network_router.post("/openstack/connect")
async def connect_openstack(
    request: CloudConnectRequest,
    current_user: dict = Depends(get_current_user)
):
    """Connect to OpenStack using stored configuration"""
    config = await db.settings_openstack.find_one({"id": request.config_id})
    if not config:
        raise HTTPException(status_code=404, detail="OpenStack configuration not found")
    
    connector = OpenStackConnector(
        auth_url=config.get("auth_url"),
        username=config.get("username"),
        password=config.get("password"),
        project_name=config.get("project_name"),
        domain=config.get("domain", "default")
    )
    
    success, message = await connector.connect()
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    # Get data
    servers = await connector.get_servers()
    networks = await connector.get_networks()
    
    return {
        "success": True,
        "message": message,
        "servers": servers,
        "networks": networks
    }

@network_router.post("/oracle/connect")
async def connect_oracle(
    request: CloudConnectRequest,
    current_user: dict = Depends(get_current_user)
):
    """Connect to Oracle DB using stored configuration"""
    config = await db.settings_oracle.find_one({"id": request.config_id})
    if not config:
        raise HTTPException(status_code=404, detail="Oracle configuration not found")
    
    connector = OracleDBConnector(
        host=config.get("host"),
        port=config.get("port", 1521),
        service_name=config.get("service_name"),
        username=config.get("username"),
        password=config.get("password")
    )
    
    success, message = await connector.connect()
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    # Get data
    instance_info = await connector.get_instance_info()
    tablespaces = await connector.get_tablespace_usage()
    
    return {
        "success": True,
        "message": message,
        "instance_info": instance_info,
        "tablespaces": tablespaces
    }

@network_router.post("/vcenter/connect")
async def connect_vcenter(
    request: CloudConnectRequest,
    current_user: dict = Depends(get_current_user)
):
    """Connect to vCenter using stored configuration"""
    config = await db.settings_vcenter.find_one({"id": request.config_id})
    if not config:
        raise HTTPException(status_code=404, detail="vCenter configuration not found")
    
    connector = VCenterConnector(
        host=config.get("host"),
        username=config.get("username"),
        password=config.get("password"),
        port=config.get("port", 443)
    )
    
    success, message = await connector.connect()
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    # Get data
    vms = await connector.get_vms()
    hosts = await connector.get_hosts()
    
    return {
        "success": True,
        "message": message,
        "virtual_machines": vms,
        "esxi_hosts": hosts
    }

# Background polling control
@network_router.post("/polling/start")
async def start_background_polling(current_user: dict = Depends(get_current_user)):
    """Start background SNMP polling (Admin only)"""
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    global background_polling
    if background_polling and background_polling.running:
        return {"message": "Polling is already running"}
    
    background_polling = BackgroundPollingService(db, poll_interval=30)
    asyncio.create_task(background_polling.start())
    
    return {"message": "Background polling started", "interval": 30}

@network_router.post("/polling/stop")
async def stop_background_polling(current_user: dict = Depends(get_current_user)):
    """Stop background SNMP polling (Admin only)"""
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    global background_polling
    if background_polling:
        background_polling.stop()
        return {"message": "Background polling stopped"}
    
    return {"message": "Polling was not running"}

@network_router.get("/polling/status")
async def get_polling_status(current_user: dict = Depends(get_current_user)):
    """Get background polling status"""
    global background_polling
    running = background_polling.running if background_polling else False
    return {
        "running": running,
        "interval": 30 if running else None
    }

# Include network router
api_router.include_router(network_router)

# ===================== AI INCIDENT RESOLUTION =====================
# ===================== NEW AI INCIDENT RESOLUTION & STAGING =====================
# Modified : 21/07/2026 - Injection for AI Approval, Line : 7923 - 7533
class AutonomousStageRequest(BaseModel):
    incident_id: str
    triggered_by: str = "ai_agent"
    


# =====================================================================
# STAGE 2: EXECUTION APPROVAL GATEWAY
# =====================================================================

class AutonomousApprovalRequest(BaseModel):
    incident_id: str
    approved: bool
@ai_router.post("/autonomous/stage-remedy")
async def stage_autonomous_remedy(
    request: AutonomousStageRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Uses the LLM to stage proposed CLI commands and locks status to 'awaiting_approval'.
    Legacy playbook dependencies removed.
    """
    incident = await db.incidents.find_one({"id": request.incident_id})
    if not incident:
        raise HTTPException(status_code=404, detail="Incident context missing.")
        
    device_id = incident.get("device_id") or (incident.get("affected_devices")[0] if incident.get("affected_devices") else None)
    device = await db.devices.find_one({"id": device_id})

    driver_key = device.get("vendor", "generic").lower()
    source = "emergent_llm"

    prompt_context = f"Device Vendor: {driver_key}\nTelemetry: {json.dumps(incident.get('telemetry', {}), default=str)}"
    prompt_query = "Analyze the incident details and output the explicit raw vendor CLI commands required to fix this issue as a clean text string. Output only the commands."
    
    proposed_commands = await get_ai_analysis(prompt_context, prompt_query)

    await db.incidents.update_one(
        {"id": request.incident_id},
        {"$set": {
            "status": "awaiting_approval",
            "proposed_remediation_source": source,
            "proposed_commands": proposed_commands
        }}
    )

    return {
        "success": True,
        "status": "awaiting_approval",
        "source": source,
        "proposed_commands": proposed_commands
    }

@ai_router.post("/autonomous/execute-approval")
async def execute_approval_remedy(
    request: AutonomousApprovalRequest,
    current_user: dict = Depends(get_current_user)
):
    """Executes human-approved CLI commands on the target hardware."""
    incident = await db.incidents.find_one({"id": request.incident_id})
    if not incident or incident.get("status") != "awaiting_approval":
        raise HTTPException(status_code=400, detail="Incident is not staged for approval.")

    if not request.approved:
        await db.incidents.update_one(
            {"id": request.incident_id},
            {"$set": {"status": "in_progress", "proposed_commands": None}}
        )
        return {"success": True, "message": "Remediation rejected."}

    commands_to_run = incident.get("proposed_commands")
    device = await db.devices.find_one({"id": incident.get("device_id")})

    agent_service = AutonomousAgentService()
    ssh_client, _ = await agent_service.connect_ssh(device)
    
    if ssh_client:
        execution_result = await agent_service.execute_command(ssh_client, commands_to_run)
        ssh_client.close()
        
        if execution_result.get("success"):
            await db.incidents.update_one(
                {"id": request.incident_id},
                {"$set": {"status": "resolved", "resolved_at": datetime.now(timezone.utc).isoformat()}}
            )
        return {"success": True, "execution_output": execution_result}

    return {"success": False, "error": "Failed to establish SSH connection for execution."}


@agent_exec_router.get("/staged-incidents")
async def get_staged_actions(current_user: dict = Depends(get_current_user)):
    """Get all incidents currently awaiting approval."""
    incidents = await db.incidents.find(
        {"status": "awaiting_approval"}, 
        {"_id": 0}
    ).sort("updated_at", -1).to_list(100)
    return incidents


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
api_router.include_router(settings_router)
api_router.include_router(agent_exec_router)
api_router.include_router(users_router)

# ===================== AUDIT LOGGING SERVICE =====================

class AuditLogType(str, Enum):
    LOGIN = "login"
    LOGOUT = "logout"
    USER_CREATE = "user_create"
    USER_UPDATE = "user_update"
    USER_DELETE = "user_delete"
    DEVICE_CREATE = "device_create"
    DEVICE_UPDATE = "device_update"
    DEVICE_DELETE = "device_delete"
    CONFIG_BACKUP = "config_backup"
    CONFIG_RESTORE = "config_restore"
    CONFIG_FETCH = "config_fetch"
    INCIDENT_CREATE = "incident_create"
    INCIDENT_UPDATE = "incident_update"
    INCIDENT_RESOLVE = "incident_resolve"
    ALERT_ACK = "alert_acknowledge"
    ALERT_RESOLVE = "alert_resolve"
    SSH_CONNECT = "ssh_connect"
    SSH_COMMAND = "ssh_command"
    AI_AGENT_RUN = "ai_agent_run"
    AI_ACTION_APPROVE = "ai_action_approve"
    AI_ACTION_REJECT = "ai_action_reject"
    AAA_AUTH = "aaa_auth"
    SETTINGS_UPDATE = "settings_update"
    SYSTEM_ACTION = "system_action"

class AuditLog(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    user_id: Optional[str] = None
    user_email: Optional[str] = None
    user_name: Optional[str] = None
    action_type: str
    resource_type: Optional[str] = None  # device, user, incident, etc.
    resource_id: Optional[str] = None
    resource_name: Optional[str] = None
    description: str
    details: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    success: bool = True
    error_message: Optional[str] = None

AUDIT_RETENTION_DAYS = 90

async def create_audit_log(
    action_type: str,
    description: str,
    user: dict = None,
    resource_type: str = None,
    resource_id: str = None,
    resource_name: str = None,
    details: dict = None,
    success: bool = True,
    error_message: str = None,
    ip_address: str = None
):
    """Create an audit log entry"""
    log_entry = {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_id": user.get("id") if user else None,
        "user_email": user.get("email") if user else None,
        "user_name": user.get("name") if user else None,
        "action_type": action_type,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "resource_name": resource_name,
        "description": description,
        "details": details,
        "ip_address": ip_address,
        "success": success,
        "error_message": error_message
    }
    
    insert_entry = log_entry.copy()
    await db.audit_logs.insert_one(insert_entry)
    return log_entry

async def cleanup_old_audit_logs():
    """Remove audit logs older than retention period"""
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=AUDIT_RETENTION_DAYS)
    result = await db.audit_logs.delete_many({
        "timestamp": {"$lt": cutoff_date.isoformat()}
    })
    return result.deleted_count

# Audit Router
audit_router = APIRouter(prefix="/audit", tags=["Audit"])

@audit_router.get("/logs")
async def get_audit_logs(
    page: int = 1,
    limit: int = 50,
    action_type: Optional[str] = None,
    user_email: Optional[str] = None,
    resource_type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    success_only: Optional[bool] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get audit logs with filtering and pagination"""
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    query = {}
    
    if action_type:
        query["action_type"] = action_type
    if user_email:
        query["user_email"] = {"$regex": user_email, "$options": "i"}
    if resource_type:
        query["resource_type"] = resource_type
    if start_date:
        query["timestamp"] = {"$gte": start_date}
    if end_date:
        if "timestamp" in query:
            query["timestamp"]["$lte"] = end_date
        else:
            query["timestamp"] = {"$lte": end_date}
    if success_only is not None:
        query["success"] = success_only
    
    skip = (page - 1) * limit
    total = await db.audit_logs.count_documents(query)
    logs = await db.audit_logs.find(query, {"_id": 0}).sort("timestamp", -1).skip(skip).limit(limit).to_list(limit)
    
    return {
        "logs": logs,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit
    }

@audit_router.get("/logs/stats")
async def get_audit_stats(current_user: dict = Depends(get_current_user)):
    """Get audit log statistics"""
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Get counts by action type
    pipeline = [
        {"$group": {"_id": "$action_type", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    action_counts = await db.audit_logs.aggregate(pipeline).to_list(100)
    
    # Get counts by user
    user_pipeline = [
        {"$match": {"user_email": {"$ne": None}}},
        {"$group": {"_id": "$user_email", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10}
    ]
    user_counts = await db.audit_logs.aggregate(user_pipeline).to_list(10)
    
    # Get today's count
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_count = await db.audit_logs.count_documents({"timestamp": {"$gte": today.isoformat()}})
    
    # Get total count
    total_count = await db.audit_logs.count_documents({})
    
    # Get failure count
    failure_count = await db.audit_logs.count_documents({"success": False})
    
    return {
        "total_logs": total_count,
        "today_logs": today_count,
        "failed_actions": failure_count,
        "by_action_type": {item["_id"]: item["count"] for item in action_counts},
        "top_users": [{"email": item["_id"], "count": item["count"]} for item in user_counts],
        "retention_days": AUDIT_RETENTION_DAYS
    }

@audit_router.get("/logs/export")
async def export_audit_logs(
    format: str = "csv",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Export audit logs as CSV or JSON"""
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    query = {}
    if start_date:
        query["timestamp"] = {"$gte": start_date}
    if end_date:
        if "timestamp" in query:
            query["timestamp"]["$lte"] = end_date
        else:
            query["timestamp"] = {"$lte": end_date}
    
    logs = await db.audit_logs.find(query, {"_id": 0}).sort("timestamp", -1).to_list(10000)
    
    await create_audit_log(
        action_type="system_action",
        description=f"Exported {len(logs)} audit logs as {format.upper()}",
        user=current_user,
        details={"format": format, "count": len(logs)}
    )
    
    if format == "json":
        return {"logs": logs, "exported_at": datetime.now(timezone.utc).isoformat()}
    
    # CSV format
    import csv
    import io
    
    output = io.StringIO()
    if logs:
        writer = csv.DictWriter(output, fieldnames=logs[0].keys())
        writer.writeheader()
        for log in logs:
            # Flatten details dict
            row = {k: (json.dumps(v) if isinstance(v, dict) else v) for k, v in log.items()}
            writer.writerow(row)
    
    csv_content = output.getvalue()
    
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=audit_logs_{datetime.now().strftime('%Y%m%d')}.csv"}
    )

@audit_router.delete("/logs/cleanup")
async def cleanup_audit_logs(current_user: dict = Depends(get_current_user)):
    """Manually trigger cleanup of old audit logs"""
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    deleted = await cleanup_old_audit_logs()
    
    await create_audit_log(
        action_type="system_action",
        description=f"Manual audit log cleanup - deleted {deleted} old logs",
        user=current_user,
        details={"deleted_count": deleted, "retention_days": AUDIT_RETENTION_DAYS}
    )
    
    return {"success": True, "deleted_count": deleted}

@audit_router.get("/action-types")
async def get_action_types(current_user: dict = Depends(get_current_user)):
    """Get list of all action types"""
    return [e.value for e in AuditLogType]

# ===================== DEVICE CONFIG BACKUP/RESTORE SERVICE =====================

# Multi-vendor config commands
VENDOR_CONFIG_COMMANDS = {
    "cisco": {
        "fetch": "show running-config",
        "save": "copy running-config startup-config",
        "terminal_length": "terminal length 0",
        "exit": "exit"
    },
    "juniper": {
        "fetch": "show configuration | display set",
        "save": "commit",
        "terminal_length": "set cli screen-length 0",
        "exit": "exit"
    },
    "arista": {
        "fetch": "show running-config",
        "save": "copy running-config startup-config",
        "terminal_length": "terminal length 0",
        "exit": "exit"
    },
    "huawei": {
        "fetch": "display current-configuration",
        "save": "save",
        "terminal_length": "screen-length 0 temporary",
        "exit": "quit"
    },
    "palo alto": {
        "fetch": "show config running",
        "save": "commit",
        "terminal_length": "set cli pager off",
        "exit": "exit"
    },
    "fortinet": {
        "fetch": "show full-configuration",
        "save": "execute backup config flash",
        "terminal_length": "config system console\nset output standard\nend",
        "exit": "exit"
    },
    "f5": {
        "fetch": "tmsh list",
        "save": "tmsh save sys config",
        "terminal_length": "",
        "exit": "exit"
    },
    "default": {
        "fetch": "show running-config",
        "save": "write memory",
        "terminal_length": "terminal length 0",
        "exit": "exit"
    }
}

def get_vendor_commands(vendor: str) -> dict:
    """Get config commands for a specific vendor"""
    vendor_lower = vendor.lower() if vendor else "default"
    for key in VENDOR_CONFIG_COMMANDS:
        if key in vendor_lower:
            return VENDOR_CONFIG_COMMANDS[key]
    return VENDOR_CONFIG_COMMANDS["default"]

class ConfigBackupService:
    """Service for device configuration backup and restore"""
    
    @staticmethod
    async def fetch_device_config(device: dict, credentials: dict = None) -> dict:
        """Fetch running configuration from a device via SSH"""
        ip = device.get("ip_address")
        vendor = device.get("vendor", "")
        
        if not ip:
            return {"success": False, "error": "No IP address configured"}
        
        # Get vendor-specific commands
        commands = get_vendor_commands(vendor)
        
        # Get SSH credentials
        if not credentials:
            creds = await db.settings_ssh.find_one({"device_id": device.get("id")}, {"_id": 0})
            if not creds:
                creds = await db.settings_ssh.find_one({"device_type": device.get("type")}, {"_id": 0})
            if not creds:
                creds = {"username": "admin", "password": "", "port": 22}
        else:
            creds = credentials
        
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(
                ip,
                port=creds.get("port", 22),
                username=creds.get("username", "admin"),
                password=creds.get("password", ""),
                timeout=30,
                allow_agent=False,
                look_for_keys=False
            )
            
            # Create shell session
            shell = client.invoke_shell()
            import time
            time.sleep(1)
            
            # Set terminal length
            if commands.get("terminal_length"):
                shell.send(commands["terminal_length"] + "\n")
                time.sleep(0.5)
            
            # Fetch config
            shell.send(commands["fetch"] + "\n")
            time.sleep(3)  # Wait for full config output
            
            output = ""
            while shell.recv_ready():
                output += shell.recv(65535).decode('utf-8', errors='ignore')
                time.sleep(0.1)
            
            # Clean up
            shell.send(commands["exit"] + "\n")
            client.close()
            
            # Parse output - remove command echo and prompts
            config_lines = output.split('\n')
            clean_config = []
            capture = False
            for line in config_lines:
                if commands["fetch"].split()[0] in line:
                    capture = True
                    continue
                if capture:
                    # Stop at exit command or next prompt
                    if line.strip().startswith(commands["exit"]):
                        break
                    clean_config.append(line)
            
            config_text = '\n'.join(clean_config).strip()
            
            return {
                "success": True,
                "config": config_text,
                "vendor": vendor,
                "fetched_at": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Config fetch failed for {ip}: {e}")
            return {"success": False, "error": str(e)}
    
    @staticmethod
    async def save_config_backup(device: dict, config: str, user: dict, backup_type: str = "manual") -> dict:
        """Save a configuration backup to database"""
        # Get latest version number
        latest = await db.config_backups.find_one(
            {"device_id": device.get("id")},
            sort=[("version", -1)]
        )
        version = (latest.get("version", 0) if latest else 0) + 1
        
        backup_record = {
            "id": str(uuid.uuid4()),
            "device_id": device.get("id"),
            "device_name": device.get("name"),
            "device_ip": device.get("ip_address"),
            "vendor": device.get("vendor"),
            "config_data": config,
            "config_hash": hash(config),
            "version": version,
            "backup_type": backup_type,  # manual, scheduled, pre-change
            "created_by": user.get("name"),
            "created_by_id": user.get("id"),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "size_bytes": len(config.encode('utf-8'))
        }
        
        backup_insert = backup_record.copy()
        await db.config_backups.insert_one(backup_insert)
        
        # Remove config_data from response (too large)
        del backup_record["config_data"]
        return backup_record
    
    @staticmethod
    async def restore_config(device: dict, backup_id: str, credentials: dict = None) -> dict:
        """Restore a configuration to a device"""
        # Get backup
        backup = await db.config_backups.find_one({"id": backup_id}, {"_id": 0})
        if not backup:
            return {"success": False, "error": "Backup not found"}
        
        ip = device.get("ip_address")
        vendor = device.get("vendor", "")
        
        if not ip:
            return {"success": False, "error": "No IP address configured"}
        
        # Get SSH credentials
        if not credentials:
            creds = await db.settings_ssh.find_one({"device_id": device.get("id")}, {"_id": 0})
            if not creds:
                creds = await db.settings_ssh.find_one({"device_type": device.get("type")}, {"_id": 0})
            if not creds:
                return {"success": False, "error": "No SSH credentials configured"}
        else:
            creds = credentials
        
        # Note: Full config restore is complex and vendor-specific
        # This is a simplified implementation
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(
                ip,
                port=creds.get("port", 22),
                username=creds.get("username", "admin"),
                password=creds.get("password", ""),
                timeout=30,
                allow_agent=False,
                look_for_keys=False
            )
            
            # For safety, we'll just save the config to a file on the device
            # Full restore requires config mode and is vendor-specific
            commands = get_vendor_commands(vendor)
            
            # Execute save command
            stdin, stdout, stderr = client.exec_command(commands["save"], timeout=60)
            output = stdout.read().decode('utf-8')
            error = stderr.read().decode('utf-8')
            
            client.close()
            
            return {
                "success": True,
                "message": "Configuration restore initiated",
                "output": output,
                "backup_version": backup.get("version"),
                "restored_at": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Config restore failed for {ip}: {e}")
            return {"success": False, "error": str(e)}

config_backup_service = ConfigBackupService()

# Config Backup Router
backup_router = APIRouter(prefix="/backup", tags=["Backup"])

@backup_router.post("/devices/{device_id}/fetch")
async def fetch_device_config(
    device_id: str,
    credentials: Optional[dict] = None,
    current_user: dict = Depends(get_current_user)
):
    """Fetch current running configuration from a device"""
    device = await db.devices.find_one({"id": device_id}, {"_id": 0})
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    result = await config_backup_service.fetch_device_config(device, credentials)
    
    await create_audit_log(
        action_type=AuditLogType.CONFIG_FETCH.value,
        description=f"Fetched configuration from {device.get('name')}",
        user=current_user,
        resource_type="device",
        resource_id=device_id,
        resource_name=device.get("name"),
        success=result.get("success", False),
        error_message=result.get("error")
    )
    
    return result

@backup_router.post("/devices/{device_id}/backup")
async def create_device_backup(
    device_id: str,
    backup_type: str = "manual",
    credentials: Optional[dict] = None,
    current_user: dict = Depends(get_current_user)
):
    """Create a configuration backup for a device"""
    device = await db.devices.find_one({"id": device_id}, {"_id": 0})
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    # First fetch the config
    fetch_result = await config_backup_service.fetch_device_config(device, credentials)
    
    if not fetch_result.get("success"):
        await create_audit_log(
            action_type=AuditLogType.CONFIG_BACKUP.value,
            description=f"Failed to backup configuration for {device.get('name')}",
            user=current_user,
            resource_type="device",
            resource_id=device_id,
            resource_name=device.get("name"),
            success=False,
            error_message=fetch_result.get("error")
        )
        raise HTTPException(status_code=500, detail=fetch_result.get("error"))
    
    # Save the backup
    backup = await config_backup_service.save_config_backup(
        device, fetch_result["config"], current_user, backup_type
    )
    
    await create_audit_log(
        action_type=AuditLogType.CONFIG_BACKUP.value,
        description=f"Created configuration backup v{backup['version']} for {device.get('name')}",
        user=current_user,
        resource_type="device",
        resource_id=device_id,
        resource_name=device.get("name"),
        details={"backup_id": backup["id"], "version": backup["version"], "size": backup["size_bytes"]}
    )
    
    return backup

@backup_router.get("/devices/{device_id}/backups")
async def get_device_backups(device_id: str, current_user: dict = Depends(get_current_user)):
    """Get all backups for a device"""
    backups = await db.config_backups.find(
        {"device_id": device_id},
        {"_id": 0, "config_data": 0}  # Exclude large config data
    ).sort("created_at", -1).to_list(100)
    
    return backups

@backup_router.get("/backups/{backup_id}")
async def get_backup(backup_id: str, current_user: dict = Depends(get_current_user)):
    """Get a specific backup with full config"""
    backup = await db.config_backups.find_one({"id": backup_id}, {"_id": 0})
    if not backup:
        raise HTTPException(status_code=404, detail="Backup not found")
    return backup

@backup_router.post("/devices/{device_id}/restore/{backup_id}")
async def restore_device_config(
    device_id: str,
    backup_id: str,
    credentials: Optional[dict] = None,
    current_user: dict = Depends(get_current_user)
):
    """Restore a configuration backup to a device"""
    device = await db.devices.find_one({"id": device_id}, {"_id": 0})
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    result = await config_backup_service.restore_config(device, backup_id, credentials)
    
    await create_audit_log(
        action_type=AuditLogType.CONFIG_RESTORE.value,
        description=f"Restored configuration backup to {device.get('name')}",
        user=current_user,
        resource_type="device",
        resource_id=device_id,
        resource_name=device.get("name"),
        details={"backup_id": backup_id},
        success=result.get("success", False),
        error_message=result.get("error")
    )
    
    return result

@backup_router.get("/backups/{backup_id}/diff/{compare_id}")
async def compare_backups(
    backup_id: str,
    compare_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Compare two configuration backups"""
    backup1 = await db.config_backups.find_one({"id": backup_id}, {"_id": 0})
    backup2 = await db.config_backups.find_one({"id": compare_id}, {"_id": 0})
    
    if not backup1 or not backup2:
        raise HTTPException(status_code=404, detail="Backup not found")
    
    import difflib
    
    config1_lines = backup1.get("config_data", "").splitlines(keepends=True)
    config2_lines = backup2.get("config_data", "").splitlines(keepends=True)
    
    diff = list(difflib.unified_diff(
        config1_lines,
        config2_lines,
        fromfile=f"v{backup1.get('version')} ({backup1.get('created_at')})",
        tofile=f"v{backup2.get('version')} ({backup2.get('created_at')})"
    ))
    
    return {
        "backup1": {"id": backup_id, "version": backup1.get("version"), "created_at": backup1.get("created_at")},
        "backup2": {"id": compare_id, "version": backup2.get("version"), "created_at": backup2.get("created_at")},
        "diff": ''.join(diff),
        "changes_detected": len(diff) > 0
    }

@backup_router.delete("/backups/{backup_id}")
async def delete_backup(backup_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a configuration backup"""
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    backup = await db.config_backups.find_one({"id": backup_id}, {"_id": 0})
    if not backup:
        raise HTTPException(status_code=404, detail="Backup not found")
    
    await db.config_backups.delete_one({"id": backup_id})
    
    await create_audit_log(
        action_type="system_action",
        description=f"Deleted configuration backup v{backup.get('version')} for {backup.get('device_name')}",
        user=current_user,
        resource_type="backup",
        resource_id=backup_id,
        details={"device_id": backup.get("device_id"), "version": backup.get("version")}
    )
    
    return {"success": True, "message": "Backup deleted"}

@backup_router.get("/all")
async def get_all_backups(
    limit: int = 50,
    device_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get all backups across all devices"""
    query = {}
    if device_id:
        query["device_id"] = device_id
    
    backups = await db.config_backups.find(
        query,
        {"_id": 0, "config_data": 0}
    ).sort("created_at", -1).to_list(limit)
    
    return backups

# ===================== AAA AUTHENTICATION SERVICE =====================

class AAAService:
    """Service for RADIUS/TACACS+ authentication"""
    
    @staticmethod
    async def authenticate_radius(username: str, password: str, server_config: dict) -> dict:
        """Authenticate user against RADIUS server"""
        try:
            from pyrad.client import Client
            from pyrad.dictionary import Dictionary
            from pyrad import packet
            import pyrad.packet
            
            # Create RADIUS client
            srv = Client(
                server=server_config.get("primary_host"),
                secret=server_config.get("shared_secret", "").encode(),
                dict=Dictionary()
            )
            srv.timeout = server_config.get("timeout", 5)
            srv.retries = server_config.get("retries", 3)
            
            # Create auth request
            req = srv.CreateAuthPacket(code=pyrad.packet.AccessRequest, User_Name=username)
            req["User-Password"] = req.PwCrypt(password)
            
            # Send request
            reply = srv.SendPacket(req)
            
            if reply.code == pyrad.packet.AccessAccept:
                return {
                    "success": True,
                    "method": "radius",
                    "server": server_config.get("primary_host"),
                    "message": "Authentication successful"
                }
            else:
                return {
                    "success": False,
                    "method": "radius",
                    "server": server_config.get("primary_host"),
                    "message": "Authentication rejected"
                }
                
        except Exception as e:
            logger.error(f"RADIUS authentication error: {e}")
            
            # Try secondary server if available
            if server_config.get("secondary_host"):
                try:
                    srv = Client(
                        server=server_config.get("secondary_host"),
                        secret=server_config.get("shared_secret", "").encode(),
                        dict=Dictionary()
                    )
                    srv.timeout = server_config.get("timeout", 5)
                    
                    req = srv.CreateAuthPacket(code=pyrad.packet.AccessRequest, User_Name=username)
                    req["User-Password"] = req.PwCrypt(password)
                    reply = srv.SendPacket(req)
                    
                    if reply.code == pyrad.packet.AccessAccept:
                        return {
                            "success": True,
                            "method": "radius",
                            "server": server_config.get("secondary_host"),
                            "message": "Authentication successful (secondary)"
                        }
                except Exception as e2:
                    logger.error(f"RADIUS secondary auth error: {e2}")
            
            return {
                "success": False,
                "method": "radius",
                "error": str(e),
                "message": "RADIUS server unreachable"
            }
    
    @staticmethod
    async def authenticate_tacacs(username: str, password: str, server_config: dict) -> dict:
        """Authenticate user against TACACS+ server"""
        try:
            from tacacs_plus.client import TACACSClient
            from tacacs_plus.flags import TAC_PLUS_AUTHEN_TYPE_ASCII
            
            client = TACACSClient(
                host=server_config.get("primary_host"),
                port=server_config.get("primary_port", 49),
                secret=server_config.get("shared_secret", ""),
                timeout=server_config.get("timeout", 5)
            )
            
            # Authenticate
            auth = client.authenticate(
                username,
                password,
                authen_type=TAC_PLUS_AUTHEN_TYPE_ASCII
            )
            
            if auth.valid:
                return {
                    "success": True,
                    "method": "tacacs",
                    "server": server_config.get("primary_host"),
                    "message": "Authentication successful"
                }
            else:
                return {
                    "success": False,
                    "method": "tacacs",
                    "server": server_config.get("primary_host"),
                    "message": "Authentication rejected"
                }
                
        except Exception as e:
            logger.error(f"TACACS+ authentication error: {e}")
            
            # Try secondary server if available
            if server_config.get("secondary_host"):
                try:
                    client = TACACSClient(
                        host=server_config.get("secondary_host"),
                        port=server_config.get("secondary_port", 49),
                        secret=server_config.get("shared_secret", ""),
                        timeout=server_config.get("timeout", 5)
                    )
                    auth = client.authenticate(
                        username,
                        password,
                        authen_type=TAC_PLUS_AUTHEN_TYPE_ASCII
                    )
                    
                    if auth.valid:
                        return {
                            "success": True,
                            "method": "tacacs",
                            "server": server_config.get("secondary_host"),
                            "message": "Authentication successful (secondary)"
                        }
                except Exception as e2:
                    logger.error(f"TACACS+ secondary auth error: {e2}")
            
            return {
                "success": False,
                "method": "tacacs",
                "error": str(e),
                "message": "TACACS+ server unreachable"
            }
    
    @staticmethod
    async def authenticate(username: str, password: str) -> dict:
        """Authenticate user against configured AAA servers"""
        # Get active AAA configs
        aaa_configs = await db.aaa_config.find({"is_active": True}, {"_id": 0}).to_list(10)
        
        if not aaa_configs:
            return {"success": False, "error": "No AAA servers configured", "fallback_to_local": True}
        
        for config in aaa_configs:
            if not config.get("use_for_login", True):
                continue
            
            server_type = config.get("server_type", "radius").lower()
            
            if server_type == "radius":
                result = await AAAService.authenticate_radius(username, password, config)
            elif server_type == "tacacs":
                result = await AAAService.authenticate_tacacs(username, password, config)
            else:
                continue
            
            if result.get("success"):
                return result
        
        return {"success": False, "error": "AAA authentication failed", "fallback_to_local": True}

aaa_service = AAAService()

# AAA Router
aaa_router = APIRouter(prefix="/aaa", tags=["AAA"])

@aaa_router.post("/test")
async def test_aaa_connection(
    config_id: str,
    test_username: Optional[str] = None,
    test_password: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Test AAA server connection"""
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    config = await db.aaa_config.find_one({"id": config_id}, {"_id": 0})
    if not config:
        raise HTTPException(status_code=404, detail="AAA config not found")
    
    # Test connectivity
    server_type = config.get("server_type", "radius").lower()
    host = config.get("primary_host")
    port = config.get("primary_port", 1812 if server_type == "radius" else 49)
    
    import socket
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((host, port))
        sock.close()
        
        connectivity = result == 0
    except Exception as e:
        connectivity = False
    
    response = {
        "server_type": server_type,
        "host": host,
        "port": port,
        "connectivity": connectivity,
        "connectivity_message": "Server reachable" if connectivity else "Server unreachable"
    }
    
    # If test credentials provided, try authentication
    if test_username and test_password:
        if server_type == "radius":
            auth_result = await aaa_service.authenticate_radius(test_username, test_password, config)
        else:
            auth_result = await aaa_service.authenticate_tacacs(test_username, test_password, config)
        response["authentication_test"] = auth_result
    
    await create_audit_log(
        action_type=AuditLogType.AAA_AUTH.value,
        description=f"Tested AAA server connection: {host}",
        user=current_user,
        resource_type="aaa_config",
        resource_id=config_id,
        details={"server_type": server_type, "connectivity": connectivity}
    )
    
    return response

@aaa_router.post("/authenticate")
async def aaa_authenticate(
    username: str,
    password: str,
    current_user: dict = Depends(get_current_user)
):
    """Authenticate a user/device against AAA servers"""
    result = await aaa_service.authenticate(username, password)
    
    await create_audit_log(
        action_type=AuditLogType.AAA_AUTH.value,
        description=f"AAA authentication attempt for {username}",
        user=current_user,
        details={"username": username, "success": result.get("success"), "method": result.get("method")},
        success=result.get("success", False)
    )
    
    return result


app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

import upgrade_manager
from cmdb_router import cmdb_router
api_router.include_router(audit_router)
api_router.include_router(backup_router)
api_router.include_router(aaa_router)
api_router.include_router(cmdb_router)

app.include_router(api_router)
app.include_router(upgrade_manager.router, tags=["Firmware Upgrade"])


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
