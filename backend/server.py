from fastapi import FastAPI, APIRouter, HTTPException, Depends, status, WebSocket, WebSocketDisconnect, Response
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
    # Enhanced device details
    mac_address: Optional[str] = None
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
    INTERFACE_BOUNCE = "interface_bounce"
    
    # Actions requiring confirmation
    DEVICE_REBOOT = "device_reboot"
    LINK_RESET = "link_reset"
    FIRMWARE_UPDATE = "firmware_update"
    FACTORY_RESET = "factory_reset"
    POWER_CYCLE = "power_cycle"
    HARDWARE_REPLACEMENT = "hardware_replacement"

# Actions that can be auto-executed without confirmation
AUTO_RESOLVE_ACTIONS = [
    ActionType.CONFIG_CORRECTION,
    ActionType.CLEAR_LOGS,
    ActionType.ROUTE_TABLE_FIX,
    ActionType.TRACEROUTE_ANALYSIS,
    ActionType.STP_LOOP_DETECTION,
    ActionType.ASYMMETRIC_ROUTING_FIX,
    ActionType.MEMORY_CLEANUP,
    ActionType.SWITCHING_LOOP_FIX,
    ActionType.ROUTING_LOOP_FIX,
    ActionType.SERVICE_RESTART,
    ActionType.INTERFACE_BOUNCE,
]

# Actions requiring user confirmation
CONFIRMATION_REQUIRED_ACTIONS = [
    ActionType.DEVICE_REBOOT,
    ActionType.LINK_RESET,
    ActionType.FIRMWARE_UPDATE,
    ActionType.FACTORY_RESET,
    ActionType.POWER_CYCLE,
    ActionType.HARDWARE_REPLACEMENT,
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
        """Use AI to analyze incident and determine required actions"""
        device_info = ""
        if device:
            device_info = f"""
Device Information:
- Name: {device.get('name', 'N/A')}
- Type: {device.get('type', 'N/A')}
- IP: {device.get('ip_address', 'N/A')}
- Vendor: {device.get('vendor', 'N/A')}
- Model: {device.get('model', 'N/A')}
- Status: {device.get('status', 'N/A')}
- OS Version: {device.get('os_version', 'N/A')}
"""
        
        context = f"""
INCIDENT DETAILS:
- Ticket: {incident.get('ticket_number', 'N/A')}
- Title: {incident.get('title', 'N/A')}
- Description: {incident.get('description', 'N/A')}
- Priority: {incident.get('priority', 'N/A')}
- Category: {incident.get('category', 'N/A')}
- Status: {incident.get('status', 'N/A')}
{device_info}

AVAILABLE AUTO-RESOLVE ACTIONS (no confirmation needed):
1. config_correction - Fix configuration errors
2. clear_logs - Clear system/application logs
3. route_table_fix - Fix routing table issues
4. traceroute_analysis - Run traceroute to detect packet drops
5. stp_loop_detection - Detect and fix STP loops
6. asymmetric_routing_fix - Fix asymmetric routing issues
7. memory_cleanup - Clean up dead memory/processes
8. switching_loop_fix - Detect and fix switching loops
9. routing_loop_fix - Detect and fix routing loops
10. service_restart - Restart affected services
11. interface_bounce - Bounce network interfaces

ACTIONS REQUIRING USER CONFIRMATION:
1. device_reboot - Full device reboot
2. link_reset - Reset network links
3. firmware_update - Update device firmware
4. factory_reset - Factory reset device
5. power_cycle - Power cycle device
6. hardware_replacement - Flag for hardware replacement
"""
        
        query = """Analyze this incident and provide a JSON response with:
1. root_cause: Brief root cause analysis
2. actions: Array of actions to take, each with:
   - action_type: One of the action types listed above
   - description: What this action will do
   - command: The CLI command to execute (if applicable)
   - risk_level: "low", "medium", "high", or "critical"
   - estimated_downtime: Expected downtime (e.g., "0 minutes", "5 minutes")
   - order: Execution order (1, 2, 3...)
3. resolution_confidence: Percentage (0-100) confidence this will resolve the issue

IMPORTANT: Return ONLY valid JSON, no markdown or explanations. Example:
{
  "root_cause": "Memory leak causing high CPU",
  "actions": [
    {"action_type": "memory_cleanup", "description": "Clear dead processes", "command": "pkill -9 zombie_proc", "risk_level": "low", "estimated_downtime": "0 minutes", "order": 1}
  ],
  "resolution_confidence": 85
}"""
        
        try:
            response = await get_ai_analysis(context, query)
            # Try to parse JSON from response
            import re
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                return json.loads(json_match.group())
            return {"root_cause": "Unable to determine", "actions": [], "resolution_confidence": 0}
        except Exception as e:
            logger.error(f"Error analyzing incident: {e}")
            return {"root_cause": str(e), "actions": [], "resolution_confidence": 0}
    
    async def connect_ssh(self, device: dict) -> tuple:
        """Connect to device via SSH"""
        settings = await self.get_agent_settings()
        
        if not settings.get('enable_real_ssh', True):
            return None, "SSH disabled - running in simulation mode"
        
        ip = device.get('ip_address')
        if not ip:
            return None, "No IP address configured"
        
        # Try to get SSH credentials from settings
        ssh_creds = await db.settings_ssh.find_one({"device_id": device.get('id')}, {"_id": 0})
        if not ssh_creds:
            # Try device-type based credentials
            ssh_creds = await db.settings_ssh.find_one({"device_type": device.get('type')}, {"_id": 0})
        
        username = ssh_creds.get('username', 'admin') if ssh_creds else 'admin'
        password = ssh_creds.get('password', '') if ssh_creds else ''
        port = ssh_creds.get('port', 22) if ssh_creds else 22
        
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(
                ip,
                port=port,
                username=username,
                password=password,
                timeout=settings.get('ssh_timeout', 30),
                allow_agent=False,
                look_for_keys=False
            )
            return client, "Connected successfully"
        except Exception as e:
            logger.warning(f"SSH connection failed to {ip}: {e}")
            return None, f"SSH connection failed: {str(e)}"
    
    async def execute_command(self, ssh_client, command: str, timeout: int = 60) -> dict:
        """Execute a command via SSH"""
        if ssh_client is None:
            # Simulation mode
            return {
                "success": True,
                "output": f"[SIMULATED] Command executed: {command}",
                "simulated": True
            }
        
        try:
            stdin, stdout, stderr = ssh_client.exec_command(command, timeout=timeout)
            output = stdout.read().decode('utf-8')
            error = stderr.read().decode('utf-8')
            
            return {
                "success": True if not error else False,
                "output": output,
                "error": error,
                "simulated": False
            }
        except Exception as e:
            return {
                "success": False,
                "output": "",
                "error": str(e),
                "simulated": False
            }
    
    async def execute_auto_action(self, action: dict, ssh_client, device: dict) -> dict:
        """Execute an auto-resolve action"""
        action_type = action.get('action_type')
        command = action.get('command')
        
        # Generate appropriate command based on action type if not provided
        if not command:
            device_type = device.get('type', 'server')
            vendor = device.get('vendor', '').lower()
            
            command_templates = {
                'config_correction': {
                    'cisco': 'show running-config | include error',
                    'default': 'cat /etc/network/interfaces'
                },
                'clear_logs': {
                    'cisco': 'clear logging',
                    'default': 'truncate -s 0 /var/log/syslog'
                },
                'route_table_fix': {
                    'cisco': 'show ip route',
                    'default': 'ip route show'
                },
                'traceroute_analysis': {
                    'cisco': 'traceroute 8.8.8.8',
                    'default': 'traceroute -n 8.8.8.8'
                },
                'stp_loop_detection': {
                    'cisco': 'show spanning-tree summary',
                    'default': 'brctl showstp br0'
                },
                'memory_cleanup': {
                    'cisco': 'clear memory',
                    'default': 'sync; echo 3 > /proc/sys/vm/drop_caches'
                },
                'service_restart': {
                    'default': 'systemctl restart networking'
                },
                'interface_bounce': {
                    'cisco': 'interface shutdown; no shutdown',
                    'default': 'ifdown eth0 && ifup eth0'
                }
            }
            
            if action_type in command_templates:
                cmd_dict = command_templates[action_type]
                command = cmd_dict.get(vendor, cmd_dict.get('default', 'echo "No command available"'))
        
        result = await self.execute_command(ssh_client, command)
        
        return {
            "action_type": action_type,
            "command": command,
            "result": result,
            "executed_at": datetime.now(timezone.utc).isoformat(),
            "success": result.get('success', False)
        }
    
    async def run_autonomous_troubleshooting(self, incident_id: str, triggered_by: str, trigger_type: str = "manual") -> dict:
        """Main function to run autonomous troubleshooting"""
        
        # Get incident
        incident = await db.incidents.find_one({"id": incident_id}, {"_id": 0})
        if not incident:
            raise HTTPException(status_code=404, detail="Incident not found")
        
        # Create execution record
        execution = AgentExecution(
            incident_id=incident_id,
            triggered_by=triggered_by,
            trigger_type=trigger_type,
            status=AgentExecutionStatus.ANALYZING
        )
        
        execution_dict = execution.model_dump()
        execution_dict["created_at"] = execution_dict["created_at"].isoformat()
        execution_dict["updated_at"] = execution_dict["updated_at"].isoformat()
        
        # Add initial log entry
        execution_dict["execution_log"].append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message": f"Agent started - triggered by {triggered_by} ({trigger_type})",
            "type": "info"
        })
        
        # Get affected device
        device = None
        if incident.get('affected_devices'):
            device_id = incident['affected_devices'][0]
            device = await db.devices.find_one({"id": device_id}, {"_id": 0})
            if device:
                execution_dict["device_id"] = device.get('id')
                execution_dict["device_ip"] = device.get('ip_address')
                execution_dict["execution_log"].append({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "message": f"Target device: {device.get('name')} ({device.get('ip_address')})",
                    "type": "info"
                })
        
        # Store a copy for insertion to avoid _id being added to our response dict
        insert_dict = execution_dict.copy()
        await db.agent_executions.insert_one(insert_dict)
        
        try:
            # Analyze incident and determine actions
            analysis = await self.analyze_incident_for_actions(incident, device)
            
            execution_dict["analysis"] = json.dumps(analysis)
            execution_dict["root_cause"] = analysis.get('root_cause', 'Unknown')
            execution_dict["planned_actions"] = analysis.get('actions', [])
            
            execution_dict["execution_log"].append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "message": f"Root cause identified: {analysis.get('root_cause', 'Unknown')}",
                "type": "analysis"
            })
            
            # Connect to device via SSH
            ssh_client = None
            if device:
                ssh_client, ssh_message = await self.connect_ssh(device)
                execution_dict["ssh_connected"] = ssh_client is not None
                execution_dict["execution_log"].append({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "message": f"SSH: {ssh_message}",
                    "type": "ssh"
                })
            
            # Process actions
            execution_dict["status"] = AgentExecutionStatus.EXECUTING.value
            await db.agent_executions.update_one(
                {"id": execution_dict["id"]},
                {"$set": execution_dict}
            )
            
            actions_executed = []
            pending_confirmations = []
            
            for action in sorted(analysis.get('actions', []), key=lambda x: x.get('order', 999)):
                action_type = action.get('action_type', '')
                
                # Check if action requires confirmation
                requires_confirmation = action_type in [a.value for a in CONFIRMATION_REQUIRED_ACTIONS]
                
                if requires_confirmation:
                    # Create pending action for confirmation
                    pending_action = PendingAction(
                        execution_id=execution_dict["id"],
                        incident_id=incident_id,
                        device_id=device.get('id') if device else None,
                        device_name=device.get('name') if device else None,
                        action_type=action_type,
                        action_description=action.get('description', ''),
                        command_to_execute=action.get('command'),
                        risk_level=action.get('risk_level', 'high'),
                        estimated_downtime=action.get('estimated_downtime')
                    )
                    
                    pending_dict = pending_action.model_dump()
                    pending_dict["requested_at"] = pending_dict["requested_at"].isoformat()
                    pending_insert = pending_dict.copy()
                    await db.pending_actions.insert_one(pending_insert)
                    
                    pending_confirmations.append({
                        "id": pending_dict["id"],
                        "action_type": action_type,
                        "description": action.get('description', ''),
                        "risk_level": action.get('risk_level', 'high')
                    })
                    
                    execution_dict["execution_log"].append({
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "message": f"⚠️ Action requires confirmation: {action_type} - {action.get('description', '')}",
                        "type": "confirmation_required"
                    })
                    
                    # Broadcast notification for confirmation
                    await ws_manager.broadcast({
                        "type": "action_confirmation_required",
                        "data": {
                            "action_id": pending_dict["id"],
                            "incident_id": incident_id,
                            "action_type": action_type,
                            "description": action.get('description', ''),
                            "device_name": device.get('name') if device else 'Unknown',
                            "risk_level": action.get('risk_level', 'high')
                        }
                    })
                else:
                    # Execute auto-resolve action
                    execution_dict["execution_log"].append({
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "message": f"Executing: {action_type} - {action.get('description', '')}",
                        "type": "executing"
                    })
                    
                    result = await self.execute_auto_action(action, ssh_client, device or {})
                    actions_executed.append(result)
                    
                    status_emoji = "✅" if result.get('success') else "❌"
                    execution_dict["execution_log"].append({
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "message": f"{status_emoji} {action_type}: {result.get('result', {}).get('output', 'Completed')[:200]}",
                        "type": "result"
                    })
            
            # Close SSH connection
            if ssh_client:
                ssh_client.close()
            
            # Update execution record
            execution_dict["executed_actions"] = actions_executed
            execution_dict["pending_confirmations"] = pending_confirmations
            execution_dict["updated_at"] = datetime.now(timezone.utc).isoformat()
            
            # Determine final status
            if pending_confirmations:
                execution_dict["status"] = AgentExecutionStatus.WAITING_CONFIRMATION.value
            elif all(a.get('success', False) for a in actions_executed):
                execution_dict["status"] = AgentExecutionStatus.COMPLETED.value
                execution_dict["incident_resolved"] = True
                execution_dict["completed_at"] = datetime.now(timezone.utc).isoformat()
                
                # Update incident status
                await db.incidents.update_one(
                    {"id": incident_id},
                    {"$set": {
                        "status": "resolved",
                        "resolution": f"Auto-resolved by AI Agent. Root cause: {analysis.get('root_cause', 'Unknown')}",
                        "resolved_at": datetime.now(timezone.utc).isoformat(),
                        "updated_at": datetime.now(timezone.utc).isoformat()
                    }}
                )
                
                execution_dict["execution_log"].append({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "message": "✅ Incident resolved successfully",
                    "type": "success"
                })
            else:
                execution_dict["status"] = AgentExecutionStatus.PARTIALLY_RESOLVED.value
                execution_dict["execution_log"].append({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "message": "⚠️ Some actions failed - manual intervention may be required",
                    "type": "warning"
                })
            
            # Generate resolution summary
            execution_dict["resolution_summary"] = await self.generate_resolution_summary(
                incident, analysis, actions_executed, pending_confirmations
            )
            
            await db.agent_executions.update_one(
                {"id": execution_dict["id"]},
                {"$set": execution_dict}
            )
            
            return execution_dict
            
        except Exception as e:
            logger.error(f"Agent execution error: {e}")
            execution_dict["status"] = AgentExecutionStatus.FAILED.value
            execution_dict["execution_log"].append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "message": f"❌ Agent failed: {str(e)}",
                "type": "error"
            })
            await db.agent_executions.update_one(
                {"id": execution_dict["id"]},
                {"$set": execution_dict}
            )
            raise HTTPException(status_code=500, detail=str(e))
    
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
    """Run ping diagnostic and return results"""
    target = request.target
    count = min(request.count, 10)  # Max 10 pings
    
    # Get device info if provided
    device = None
    if request.device_id:
        device = await db.devices.find_one({"id": request.device_id}, {"_id": 0})
    
    # Simulate ping results (in production, would execute real ping via SSH or locally)
    import random
    ping_results = []
    packets_sent = count
    packets_received = 0
    total_time = 0
    
    for i in range(count):
        # Simulate realistic ping behavior
        success = random.random() > 0.1  # 90% success rate simulation
        latency = random.uniform(1, 100) if success else None
        
        ping_results.append({
            "seq": i + 1,
            "success": success,
            "latency_ms": round(latency, 2) if latency else None,
            "ttl": 64 if success else None,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        if success:
            packets_received += 1
            total_time += latency
    
    packet_loss = ((packets_sent - packets_received) / packets_sent) * 100
    avg_latency = total_time / packets_received if packets_received > 0 else None
    
    result = {
        "target": target,
        "device_name": device.get('name') if device else None,
        "device_ip": device.get('ip_address') if device else target,
        "packets_sent": packets_sent,
        "packets_received": packets_received,
        "packet_loss_percent": round(packet_loss, 1),
        "avg_latency_ms": round(avg_latency, 2) if avg_latency else None,
        "min_latency_ms": round(min([r['latency_ms'] for r in ping_results if r['latency_ms']], default=0), 2),
        "max_latency_ms": round(max([r['latency_ms'] for r in ping_results if r['latency_ms']], default=0), 2),
        "ping_results": ping_results,
        "status": "reachable" if packet_loss < 100 else "unreachable",
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
    """Run traceroute diagnostic and return hop-by-hop results"""
    target = request.target
    max_hops = min(request.max_hops, 30)
    
    # Get device info if provided
    device = None
    if request.device_id:
        device = await db.devices.find_one({"id": request.device_id}, {"_id": 0})
    
    # Simulate traceroute results with realistic hop data
    import random
    
    # Simulated network path
    hop_templates = [
        {"name": "gateway.local", "ip": "192.168.1.1", "type": "gateway"},
        {"name": "isp-edge-router", "ip": "10.0.0.1", "type": "router"},
        {"name": "core-router-1.isp.net", "ip": "203.0.113.1", "type": "router"},
        {"name": "backbone-node.isp.net", "ip": "203.0.113.10", "type": "backbone"},
        {"name": "peering-exchange", "ip": "198.51.100.1", "type": "exchange"},
        {"name": "cdn-edge-server", "ip": "198.51.100.50", "type": "cdn"},
        {"name": "datacenter-gw", "ip": "172.16.0.1", "type": "datacenter"},
        {"name": target, "ip": target if '.' in target else "8.8.8.8", "type": "destination"},
    ]
    
    hops = []
    num_hops = random.randint(5, min(len(hop_templates), max_hops))
    
    for i in range(num_hops):
        template = hop_templates[min(i, len(hop_templates) - 1)]
        
        # Simulate latency increasing with hops
        base_latency = 5 + (i * 8) + random.uniform(-3, 10)
        
        # Simulate occasional packet loss or timeout
        is_timeout = random.random() < 0.05
        
        hop_data = {
            "hop": i + 1,
            "ip": template["ip"] if not is_timeout else None,
            "hostname": template["name"] if not is_timeout else None,
            "type": template["type"],
            "latency_1": round(base_latency + random.uniform(-2, 2), 2) if not is_timeout else None,
            "latency_2": round(base_latency + random.uniform(-2, 2), 2) if not is_timeout else None,
            "latency_3": round(base_latency + random.uniform(-2, 2), 2) if not is_timeout else None,
            "avg_latency": round(base_latency, 2) if not is_timeout else None,
            "status": "timeout" if is_timeout else "ok",
            "is_destination": i == num_hops - 1
        }
        
        hops.append(hop_data)
    
    # Detect potential issues
    issues = []
    for i, hop in enumerate(hops):
        if hop["status"] == "timeout":
            issues.append(f"Hop {hop['hop']}: Timeout - possible firewall or routing issue")
        elif i > 0 and hop["avg_latency"] and hops[i-1]["avg_latency"]:
            latency_jump = hop["avg_latency"] - hops[i-1]["avg_latency"]
            if latency_jump > 50:
                issues.append(f"Hop {hop['hop']}: High latency jump (+{latency_jump:.0f}ms) - possible congestion")
    
    result = {
        "target": target,
        "device_name": device.get('name') if device else None,
        "device_ip": device.get('ip_address') if device else None,
        "total_hops": len(hops),
        "destination_reached": hops[-1]["is_destination"] if hops else False,
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
        {"name": "Core-Router-01", "type": "router", "ip_address": "10.0.1.1", "location": "DC-East", "vendor": "Cisco", "model": "ASR 9000", "status": "online", "mac_address": "00:1A:2B:3C:4D:01", "hostname": "core-rtr-01.dc-east.atech.local", "os_version": "IOS-XR 7.5.2", "os_install_date": "2024-03-15", "warranty_status": "active", "warranty_expiry": "2027-03-15", "aaa_enabled": True},
        {"name": "Core-Switch-01", "type": "switch", "ip_address": "10.0.1.2", "location": "DC-East", "vendor": "Cisco", "model": "Catalyst 9500", "status": "online", "mac_address": "00:1A:2B:3C:4D:02", "hostname": "core-sw-01.dc-east.atech.local", "os_version": "IOS-XE 17.6.3", "os_install_date": "2024-01-20", "warranty_status": "active", "warranty_expiry": "2026-12-31", "aaa_enabled": True},
        {"name": "Firewall-01", "type": "firewall", "ip_address": "10.0.1.3", "location": "DC-East", "vendor": "Palo Alto", "model": "PA-5260", "status": "online", "mac_address": "00:1A:2B:3C:4D:03", "hostname": "fw-01.dc-east.atech.local", "os_version": "PAN-OS 11.0.2", "os_install_date": "2024-06-01", "warranty_status": "active", "warranty_expiry": "2028-06-01", "aaa_enabled": True},
        {"name": "Load-Balancer-01", "type": "load_balancer", "ip_address": "10.0.1.4", "location": "DC-East", "vendor": "F5", "model": "BIG-IP i5800", "status": "online", "mac_address": "00:1A:2B:3C:4D:04", "hostname": "lb-01.dc-east.atech.local", "os_version": "TMOS 16.1.3", "os_install_date": "2023-09-15", "warranty_status": "active", "warranty_expiry": "2026-09-15", "aaa_enabled": False},
        {"name": "Server-Web-01", "type": "server", "ip_address": "10.0.2.10", "location": "DC-East", "vendor": "Dell", "model": "PowerEdge R750", "status": "online", "mac_address": "00:1A:2B:3C:4D:10", "hostname": "web-srv-01.dc-east.atech.local", "os_version": "RHEL 8.8", "os_install_date": "2024-02-01", "warranty_status": "active", "warranty_expiry": "2027-02-01", "aaa_enabled": False},
        {"name": "Server-Web-02", "type": "server", "ip_address": "10.0.2.11", "location": "DC-East", "vendor": "Dell", "model": "PowerEdge R750", "status": "degraded", "mac_address": "00:1A:2B:3C:4D:11", "hostname": "web-srv-02.dc-east.atech.local", "os_version": "RHEL 7.9", "os_install_date": "2022-06-15", "warranty_status": "expiring_soon", "warranty_expiry": "2025-06-15", "aaa_enabled": False},
        {"name": "Server-DB-01", "type": "server", "ip_address": "10.0.3.10", "location": "DC-East", "vendor": "HP", "model": "ProLiant DL380", "status": "online", "mac_address": "00:1A:2B:3C:4D:20", "hostname": "db-srv-01.dc-east.atech.local", "os_version": "Oracle Linux 8.7", "os_install_date": "2023-11-01", "warranty_status": "active", "warranty_expiry": "2026-11-01", "aaa_enabled": True},
        {"name": "AWS-Instance-01", "type": "cloud_instance", "ip_address": "172.31.1.10", "location": "AWS-us-east-1", "vendor": "AWS", "model": "c5.xlarge", "status": "online", "hostname": "aws-app-01.us-east-1.compute.internal", "os_version": "Amazon Linux 2023", "os_install_date": "2024-08-01", "warranty_status": "active", "aaa_enabled": False},
        {"name": "Azure-VM-01", "type": "cloud_instance", "ip_address": "172.16.1.10", "location": "Azure-EastUS", "vendor": "Azure", "model": "Standard_D4s_v3", "status": "online", "hostname": "azure-vm-01.eastus.cloudapp.azure.com", "os_version": "Windows Server 2022", "os_install_date": "2024-04-15", "warranty_status": "active", "aaa_enabled": False},
        {"name": "Edge-Router-NYC", "type": "router", "ip_address": "10.1.1.1", "location": "NYC-Office", "vendor": "Juniper", "model": "MX240", "status": "online", "mac_address": "00:1A:2B:3C:5D:01", "hostname": "edge-rtr-nyc.atech.local", "os_version": "Junos 21.4R3", "os_install_date": "2023-03-01", "warranty_status": "active", "warranty_expiry": "2026-03-01", "aaa_enabled": True},
        {"name": "Edge-Switch-NYC", "type": "switch", "ip_address": "10.1.1.2", "location": "NYC-Office", "vendor": "Arista", "model": "7050X3", "status": "offline", "mac_address": "00:1A:2B:3C:5D:02", "hostname": "edge-sw-nyc.atech.local", "os_version": "EOS 4.28.1F", "os_install_date": "2022-01-15", "warranty_status": "expired", "warranty_expiry": "2024-01-15", "aaa_enabled": True},
        {"name": "WiFi-AP-Floor1", "type": "access_point", "ip_address": "10.1.2.10", "location": "NYC-Office", "vendor": "Aruba", "model": "AP-535", "status": "online", "mac_address": "00:1A:2B:3C:5D:10", "hostname": "wifi-ap-f1.nyc.atech.local", "os_version": "ArubaOS 8.10.0.4", "os_install_date": "2024-05-01", "warranty_status": "active", "warranty_expiry": "2027-05-01", "aaa_enabled": True},
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
    except smtplib.SMTPAuthenticationError:
        raise HTTPException(status_code=400, detail="Authentication failed. Please check your username and password.")
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

# ===================== AI INCIDENT RESOLUTION =====================
@ai_router.post("/incidents/{incident_id}/analyze")
async def ai_analyze_incident(incident_id: str, current_user: dict = Depends(get_current_user)):
    """AI analyzes incident and suggests resolution"""
    incident = await db.incidents.find_one({"id": incident_id}, {"_id": 0})
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    
    # Get related device and alerts
    device = None
    if incident.get("device_id"):
        device = await db.devices.find_one({"id": incident["device_id"]}, {"_id": 0})
    
    alerts = await db.alerts.find({"incident_id": incident_id}, {"_id": 0}).to_list(100)
    
    # Build context for AI analysis
    context = f"""
    Incident: {incident.get('title', 'Unknown')}
    Description: {incident.get('description', 'No description')}
    Priority: {incident.get('priority', 'Unknown')}
    Status: {incident.get('status', 'Unknown')}
    Device: {device.get('name', 'Unknown') if device else 'No device'}
    Device Type: {device.get('type', 'Unknown') if device else 'N/A'}
    Device Status: {device.get('status', 'Unknown') if device else 'N/A'}
    Related Alerts: {len(alerts)}
    """
    
    # Get AI analysis
    analysis = await get_ai_analysis(context, "Analyze this incident and provide: 1) Root cause analysis, 2) Recommended actions, 3) Whether this can be auto-resolved or requires user confirmation")
    
    # Determine action type based on analysis
    action_type = "auto_resolve"
    requires_confirmation = False
    
    analysis_lower = analysis.lower()
    if "reboot" in analysis_lower or "restart" in analysis_lower:
        action_type = "reboot_required"
        requires_confirmation = True
    elif "disconnect" in analysis_lower or "link" in analysis_lower:
        action_type = "link_reset"
        requires_confirmation = True
    elif "hardware" in analysis_lower and ("failure" in analysis_lower or "fault" in analysis_lower):
        action_type = "hardware_failure"
        requires_confirmation = False  # SOS sent automatically
    
    # Create incident action record
    action = IncidentAction(
        incident_id=incident_id,
        action_type=action_type,
        description=analysis,
        requires_confirmation=requires_confirmation,
        confirmation_status="pending" if requires_confirmation else None
    )
    
    action_dict = action.model_dump()
    action_dict["created_at"] = action_dict["created_at"].isoformat()
    await db.incident_actions.insert_one(dict(action_dict))
    
    # If hardware failure, send SOS to all escalation contacts
    sos_sent = False
    if action_type == "hardware_failure":
        escalation_contacts = await db.escalation_contacts.find({}, {"_id": 0}).to_list(100)
        if escalation_contacts:
            # Get email config
            email_config = await db.email_config.find_one({}, {"_id": 0})
            if email_config:
                try:
                    msg = MIMEMultipart()
                    msg['From'] = f"{email_config.get('sender_name', 'NOC')} <{email_config['sender_email']}>"
                    msg['To'] = ', '.join([c["email"] for c in escalation_contacts])
                    msg['Subject'] = f"🚨 SOS: HARDWARE FAILURE - {incident.get('title', 'Critical Alert')}"
                    
                    body = f"""
                    <html>
                    <body style="font-family: Arial, sans-serif;">
                        <h2 style="color: #dc2626;">🚨 HARDWARE FAILURE DETECTED</h2>
                        <h3>{incident.get('title', 'Critical Incident')}</h3>
                        <p><strong>Device:</strong> {device.get('name', 'Unknown') if device else 'Unknown'}</p>
                        <p><strong>Description:</strong> {incident.get('description', 'No description')}</p>
                        <hr>
                        <h4>AI Analysis:</h4>
                        <p>{analysis}</p>
                        <hr>
                        <p style="color: #dc2626;"><strong>IMMEDIATE ATTENTION REQUIRED</strong></p>
                        <p>This is an automated SOS alert from ATECH NOC Commander.</p>
                    </body>
                    </html>
                    """
                    msg.attach(MIMEText(body, 'html'))
                    
                    with smtplib.SMTP(email_config['smtp_server'], email_config['smtp_port']) as server:
                        if email_config.get('use_tls', True):
                            server.starttls()
                        server.login(email_config['username'], email_config['password'])
                        server.send_message(msg)
                    sos_sent = True
                except Exception as e:
                    logger.error(f"Failed to send SOS email: {e}")
    
    return {
        "analysis": analysis,
        "action_type": action_type,
        "requires_confirmation": requires_confirmation,
        "action_id": action.id,
        "sos_sent": sos_sent
    }

@ai_router.post("/incidents/actions/{action_id}/confirm")
async def confirm_incident_action(action_id: str, approved: bool, current_user: dict = Depends(get_current_user)):
    """Confirm or reject an AI-suggested incident action"""
    action = await db.incident_actions.find_one({"id": action_id}, {"_id": 0})
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    
    status = "approved" if approved else "rejected"
    await db.incident_actions.update_one(
        {"id": action_id},
        {"$set": {
            "confirmation_status": status,
            "confirmed_by": current_user["name"]
        }}
    )
    
    result = {"message": f"Action {status}", "executed": False}
    
    # If approved, execute the action (simulated)
    if approved:
        await db.incident_actions.update_one(
            {"id": action_id},
            {"$set": {
                "executed": True,
                "executed_at": datetime.now(timezone.utc).isoformat(),
                "result": "Action executed successfully"
            }}
        )
        
        # Update incident status
        await db.incidents.update_one(
            {"id": action.get("incident_id")},
            {"$set": {"status": "in_progress", "ai_action_taken": True}}
        )
        result["executed"] = True
        result["message"] = "Action approved and executed"
    
    return result

@ai_router.get("/incidents/actions/pending")
async def get_ai_pending_actions(current_user: dict = Depends(get_current_user)):
    """Get all pending actions requiring user confirmation"""
    actions = await db.incident_actions.find(
        {"requires_confirmation": True, "confirmation_status": "pending"},
        {"_id": 0}
    ).to_list(100)
    return actions

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
