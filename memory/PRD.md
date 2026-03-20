# ATECH NOC Commander - AI-Powered Network Operation Center Tool

## Project Overview
A comprehensive NOC (Network Operation Center) tool where AI agents act as NOC engineers, providing 24x7 monitoring, incident management, and intelligent troubleshooting capabilities.

## Branding
- **Product Name**: ATECH NOC COMMANDER
- **Company**: Ameya Technology

## What's Been Implemented

### Phase 1-4 - Core Features (Complete)
- ✅ JWT Authentication
- ✅ Dashboard with KPIs
- ✅ Device Monitoring with CRUD
- ✅ Alert & Incident Management
- ✅ AI-powered troubleshooting (GPT-5.2)
- ✅ Performance Charts
- ✅ Asset Management
- ✅ Reports Generation
- ✅ SLA Tracking
- ✅ Real-time WebSocket alerts
- ✅ Network Topology (interactive, 3D icons, draggable)
- ✅ SSH Terminal
- ✅ AI Agent System with activation codes
- ✅ Multi-Level Escalation

### Phase 5 - Settings & Configuration (2026-03-18)
- ✅ Settings page with tabbed interface
- ✅ Office 365 Email Configuration
- ✅ SNMP v1/v2c Community Strings
- ✅ SNMP v3 Configuration

### Phase 6 - Major Enhancements (2026-03-20)

#### 1. Autonomous Incident Resolution with AI
- ✅ AI analyzes incidents and suggests resolutions
- ✅ Auto-resolve configuration errors automatically
- ✅ **Requires user confirmation** for reboot/reset actions
- ✅ **SOS alerts** sent to ALL escalation stakeholders on hardware failure
- API Endpoints:
  - `POST /api/ai/incidents/{id}/analyze` - AI analysis with action suggestion
  - `POST /api/ai/incidents/actions/{id}/confirm` - Approve/reject actions
  - `GET /api/ai/incidents/actions/pending` - List pending confirmations

#### 2. OpenStack Monitoring Configuration
- ✅ Full OpenStack integration settings
- ✅ Monitor all services: Nova, Neutron, Cinder, Keystone, Glance, Heat, Swift
- ✅ Auth URL, credentials, project, region configuration

#### 3. Oracle Database Monitoring Configuration
- ✅ Oracle DB connection settings
- ✅ Monitor all metrics: Tablespace, Sessions, Locks, Performance, ASM, DataGuard, RMAN
- ✅ Configurable alert thresholds

#### 4. VMware vCenter Monitoring Configuration
- ✅ vCenter connection settings
- ✅ Monitor: VMs, ESXi hosts, Datastores, Clusters, Networks, Resource Pools
- ✅ Configurable CPU/Memory/Datastore alert thresholds

#### 5. Downloadable Reports
- ✅ **PDF Download** with reportlab
- ✅ **CSV Download** 
- ✅ Report preview in modal
- ✅ Professional formatted reports with ATECH branding

#### 6. Backup Scheduling & Management
- ✅ Multiple backup methods: TFTP, SCP, SSH Command, API-based
- ✅ Schedule configuration: Daily, Weekly, Monthly with time selection
- ✅ Retention policy (days)
- ✅ Manual backup trigger button
- ✅ Target device/application selection

#### 7. AAA Server Authentication
- ✅ **RADIUS support** (port 1812 default)
- ✅ **TACACS+ support** (port 49 default)
- ✅ Primary and secondary server configuration
- ✅ Shared secret management
- ✅ Options for NOC login and device authentication

#### 8. Custom Dashboard Framework
- ✅ Dashboard templates API endpoint
- ✅ Pre-defined templates: OpenStack Monitoring, Oracle Performance, vCenter Overview
- ✅ Widget definitions with metric mappings
- ✅ CRUD for custom dashboards

### Phase 7 - AI Troubleshooting & Device Details (2026-03-20)

#### 1. Right-Click AI Troubleshooting Context Menu
- ✅ **Incidents Page**: Right-click on any incident row to get AI Troubleshoot option
- ✅ **Alerts Page**: Right-click on any alert row to get AI Troubleshoot option
- ✅ AI Troubleshooting Report modal with detailed analysis:
  - Incident Summary / Alert Assessment
  - Root Cause Analysis / Probable Cause
  - Troubleshooting Steps / Commands
  - Recommended Actions / Resolution Steps
  - Prevention Measures / Monitoring Recommendations
  - Escalation Recommendation
- ✅ Report stored in `troubleshoot_reports` collection
- API Endpoints:
  - `POST /api/incidents/{id}/ai-troubleshoot` - Full AI troubleshooting for incident
  - `POST /api/alerts/{id}/ai-troubleshoot` - Full AI troubleshooting for alert

#### 2. Enhanced Device Details View
- ✅ **Tabbed Interface**: General, Network, System tabs
- ✅ **General Tab**: IP Address, MAC Address, Hostname, Location, Vendor, Model, Serial Number
- ✅ **Network Tab**: CPU/Memory Usage with progress bars, Uptime, AAA Authentication status
- ✅ **System Tab**: OS Version, OS Install Date, Firmware Version, Warranty Status
- ✅ **Outdated OS Warning**: Amber badge when OS is >1 year old
- ✅ **Warranty Status Badges**: Active (green), Expired (red), Expiring Soon (amber)
- ✅ **AAA Badge**: Purple "AAA" badge for devices with AAA enabled
- ✅ **Attention Required Section**: Lists warnings for outdated OS and warranty issues

#### 3. Autonomous AI Agent (Auto-Fix) - NEW
- ✅ **Context Menu**: "Run AI Agent (Auto-Fix)" as primary option on incidents
- ✅ **AI Analysis**: Uses GPT-5.2 to analyze incident and determine required actions
- ✅ **Auto-Resolve Actions** (no confirmation needed):
  - Configuration corrections
  - Clear logs
  - Route table fixes
  - Traceroute analysis
  - STP loop detection
  - Asymmetric routing detection
  - Dead memory cleanup
  - Switching/Routing loop fixes
  - Service restarts
  - Interface bounce
- ✅ **Actions Requiring Confirmation**:
  - Device reboot
  - Link/Interface reset
  - Firmware update
  - Factory reset
  - Power cycle
  - Hardware replacement
- ✅ **Notification Bell**: Shows pending action count in header
- ✅ **Pending Actions Panel**: Lists actions needing approval with details
- ✅ **Confirmation Dialog**: Shows command, risk level, estimated downtime, warning
- ✅ **Agent Execution Panel**: Shows real-time execution log with timestamps
- ✅ **SSH Simulation Mode**: Runs in simulation when credentials not configured
- ✅ **Auto-Trigger Option**: Can be enabled in settings to trigger on incident creation
- API Endpoints:
  - `POST /api/agent-exec/run/{incident_id}` - Run agent on incident
  - `GET /api/agent-exec/executions` - Get all executions
  - `GET /api/agent-exec/pending-actions` - Get pending confirmations
  - `GET /api/agent-exec/pending-actions/count` - Get pending count
  - `POST /api/agent-exec/actions/{id}/approve` - Approve and execute action
  - `POST /api/agent-exec/actions/{id}/reject` - Reject action
  - `GET/PUT /api/agent-exec/settings` - Agent settings

## New Settings Tabs (Phase 6)
| Tab | Purpose |
|-----|---------|
| Email | Office 365 SMTP configuration |
| SNMP | v1/v2c community strings, v3 with auth/privacy |
| OpenStack | Cloud infrastructure monitoring |
| Oracle | Database monitoring |
| vCenter | VMware infrastructure monitoring |
| AAA | RADIUS/TACACS+ authentication |
| Backup | Scheduled backups with TFTP/SCP/SSH/API |

## New API Endpoints (Phase 6 & 7)
### Settings
- `/api/settings/openstack` - OpenStack CRUD
- `/api/settings/oracle` - Oracle DB CRUD
- `/api/settings/vcenter` - vCenter CRUD
- `/api/settings/aaa` - AAA Server CRUD
- `/api/settings/backup` - Backup config CRUD
- `/api/settings/backup/{id}/trigger` - Manual backup trigger
- `/api/settings/dashboards` - Custom dashboards CRUD
- `/api/settings/dashboards/templates` - Pre-built templates

### Reports
- `/api/reports/{id}/download/pdf` - PDF download
- `/api/reports/{id}/download/csv` - CSV download

### AI Troubleshooting (Phase 7 - NEW)
- `/api/incidents/{id}/ai-troubleshoot` - AI troubleshooting report for incident
- `/api/alerts/{id}/ai-troubleshoot` - AI troubleshooting report for alert

## Database Collections (New)
- `openstack_config` - OpenStack settings
- `oracle_config` - Oracle DB settings  
- `vcenter_config` - vCenter settings
- `aaa_config` - RADIUS/TACACS+ settings
- `backup_config` - Backup schedules
- `backup_jobs` - Backup job history
- `custom_dashboards` - User dashboards
- `incident_actions` - AI action tracking
- `troubleshoot_reports` - AI troubleshooting reports (Phase 7)
- `agent_executions` - Autonomous agent execution records (Phase 7)
- `pending_actions` - Actions awaiting user confirmation (Phase 7)
- `agent_settings` - Global agent configuration (Phase 7)

## Device Model (Enhanced - Phase 7)
```python
Device:
  - id, name, type, ip_address, location, status
  - vendor, model, serial_number, firmware_version
  - config_url, last_seen, cpu_usage, memory_usage, uptime_hours
  - tags, created_at
  # NEW Fields (Phase 7)
  - mac_address: Optional[str]
  - hostname: Optional[str]
  - os_version: Optional[str]
  - os_install_date: Optional[str]  # For >1 year check
  - warranty_status: Optional[str]  # active, expired, expiring_soon
  - warranty_expiry: Optional[str]
  - aaa_enabled: bool
  - device_description: Optional[str]
```

## Pending/Future Items
1. 🟡 Implement actual SNMP polling with pysnmp
2. 🟡 Connect to real OpenStack/Oracle/vCenter APIs
3. 🟡 Build drag-drop dashboard editor UI
4. 🟡 Mobile responsive design
5. 🟡 Audit logging

## Test Credentials
- Email: admin@noc.com
- Password: admin123
