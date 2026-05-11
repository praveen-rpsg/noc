# ATECH NOC COMMANDER - Application Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           ATECH NOC COMMANDER                                    │
│                    AI-Powered Network Operation Center                           │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT LAYER                                        │
├─────────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐             │
│  │   Web Browser   │    │ Desktop (Win)   │    │ Desktop (Mac)   │             │
│  │   React SPA     │    │ Electron App    │    │ Electron App    │             │
│  └────────┬────────┘    └────────┬────────┘    └────────┬────────┘             │
│           │                      │                      │                       │
│           └──────────────────────┼──────────────────────┘                       │
│                                  │                                              │
│                         HTTPS / WebSocket                                       │
└──────────────────────────────────┼──────────────────────────────────────────────┘
                                   │
┌──────────────────────────────────┼──────────────────────────────────────────────┐
│                              API LAYER                                          │
├──────────────────────────────────┼──────────────────────────────────────────────┤
│                                  ▼                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                      FastAPI Backend (server.py)                         │   │
│  │                          Port 8001 → /api/*                              │   │
│  ├─────────────────────────────────────────────────────────────────────────┤   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐      │   │
│  │  │   Auth   │ │ Devices  │ │ Alerts   │ │Incidents │ │ Reports  │      │   │
│  │  │  Router  │ │  Router  │ │  Router  │ │  Router  │ │  Router  │      │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘      │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐      │   │
│  │  │  Assets  │ │ Network  │ │ Settings │ │  Agents  │ │  Audit   │      │   │
│  │  │  Router  │ │  Router  │ │  Router  │ │  Router  │ │  Router  │      │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘      │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────┘
                                   │
┌──────────────────────────────────┼──────────────────────────────────────────────┐
│                           SERVICE LAYER                                         │
├──────────────────────────────────┼──────────────────────────────────────────────┤
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐             │
│  │   agents.py     │    │network_services │    │  External APIs  │             │
│  │ (AI/LLM Logic)  │    │  (SNMP/SSH)     │    │ (O365/Cloud)    │             │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘             │
└─────────────────────────────────────────────────────────────────────────────────┘
                                   │
┌──────────────────────────────────┼──────────────────────────────────────────────┐
│                            DATA LAYER                                           │
├──────────────────────────────────┼──────────────────────────────────────────────┤
│                                  ▼                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                         MongoDB Database                                 │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐           │   │
│  │  │  users  │ │ devices │ │ alerts  │ │incidents│ │ assets  │           │   │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘           │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐           │   │
│  │  │ reports │ │sla_rec. │ │ configs │ │audit_log│ │ backups │           │   │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘           │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Directory Structure

```
/app/
├── backend/                          # FastAPI Backend
│   ├── server.py                     # Main application (6809 lines)
│   ├── agents.py                     # AI/LLM integration (110 lines)
│   ├── network_services.py           # SNMP/SSH services (1040 lines)
│   ├── requirements.txt              # Python dependencies
│   ├── .env                          # Environment variables
│   └── tests/                        # Pytest test suites
│
├── frontend/                         # React Frontend
│   ├── src/
│   │   ├── App.js                    # Main app router
│   │   ├── App.css                   # Global styles
│   │   ├── pages/                    # Page components (22 pages)
│   │   ├── components/               # Reusable components
│   │   ├── services/                 # API & utility services
│   │   └── context/                  # React context providers
│   ├── electron/                     # Desktop app wrapper
│   ├── package.json                  # Node dependencies
│   └── .env                          # Frontend environment
│
├── memory/                           # Documentation
│   └── PRD.md                        # Product Requirements
│
└── test_reports/                     # Test results
```

---

## Backend Files (FastAPI + Python)

### Core Application

| File | Lines | Role |
|------|-------|------|
| `server.py` | 6809 | **Main API Server** - Contains all FastAPI routes, Pydantic models, database operations, report generation, WebSocket handlers |
| `agents.py` | 110 | **AI Integration** - Emergent LLM key management, AI troubleshooting prompts |
| `network_services.py` | 1040 | **Network Operations** - SNMP polling (pysnmp), SSH connections (paramiko), device discovery, subnet scanning |

### server.py Internal Structure

```
server.py
├── Imports & Configuration (Lines 1-50)
├── Database Setup - MongoDB/Motor (Lines 51-70)
├── Pydantic Models (Lines 71-500)
│   ├── User, Device, Alert, Incident
│   ├── Asset, Report, SLA
│   └── Config models (SNMP, AAA, Backup, etc.)
├── Authentication (Lines 501-650)
│   ├── JWT token creation/validation
│   ├── Password hashing (bcrypt)
│   └── get_current_user dependency
├── API Routers (Lines 651-6500)
│   ├── /api/auth/* - Login, Register
│   ├── /api/devices/* - Device CRUD
│   ├── /api/alerts/* - Alert management
│   ├── /api/incidents/* - Incident handling
│   ├── /api/assets/* - Asset inventory
│   ├── /api/reports/* - Report generation & download
│   ├── /api/performance/* - Metrics
│   ├── /api/sla/* - SLA tracking
│   ├── /api/agents/* - AI agents
│   ├── /api/escalation/* - Escalation rules
│   ├── /api/network/* - Discovery, SNMP, SSH
│   ├── /api/settings/* - All configurations
│   ├── /api/audit/* - Audit logging
│   ├── /api/backup/* - Config backup/restore
│   ├── /api/users/* - User management
│   └── /api/dashboard/* - Dashboard layouts
├── Helper Functions (Lines 6501-6700)
│   ├── Report generation logic
│   ├── Email sending (MS Graph/SMTP)
│   └── Audit logging
└── App Startup (Lines 6701-6809)
    ├── Router mounting
    ├── CORS configuration
    └── Background tasks
```

---

## Frontend Files (React)

### Pages Directory (`/frontend/src/pages/`)

| File | Size | Purpose |
|------|------|---------|
| `DashboardPage.js` | 19KB | **Main Dashboard** - KPI cards, charts, recent activity, quick actions |
| `DashboardEditorPage.js` | 20KB | **Drag & Drop Dashboard** - react-grid-layout, widget management |
| `MonitoringPage.js` | 33KB | **Device Monitoring** - Device list, status, metrics, polling |
| `TopologyPage.js` | 36KB | **Network Topology** - Interactive 3D topology map, node connections |
| `AlertsPage.js` | 20KB | **Alert Management** - Alert list, AI troubleshoot, context menu |
| `IncidentsPage.js` | 42KB | **Incident Management** - Incident CRUD, AI agent, diagnostics |
| `AssetsPage.js` | 21KB | **Asset Inventory** - Asset CRUD, warranty tracking |
| `ReportsPage.js` | 30KB | **Reports** - Generate, preview, download (PDF/CSV) |
| `PerformancePage.js` | 12KB | **Performance Metrics** - Charts, graphs, historical data |
| `SLAPage.js` | 11KB | **SLA Management** - SLA tracking, compliance |
| `SSHTerminalPage.js` | 14KB | **SSH Terminal** - Direct SSH to devices |
| `AgentsPage.js` | 21KB | **AI Agents** - Agent management, execution history |
| `EscalationPage.js` | 15KB | **Escalation Rules** - Multi-level escalation config |
| `SettingsPage.js` | 61KB | **Settings Hub** - Email, SNMP, Cloud, AAA, Backup configs |
| `NetworkDiscoveryPage.js` | 23KB | **Network Discovery** - Subnet scanning, device detection |
| `ConfigBackupPage.js` | 27KB | **Config Backup** - Multi-vendor config backup/restore |
| `AuditLogsPage.js` | 24KB | **Audit Logs** - 90-day retention, filters, export |
| `UserManagementPage.js` | 27KB | **User Management** - Admin/Operator roles, CRUD |
| `ConfigurationPage.js` | 10KB | **General Config** - Notification thresholds |
| `LoginPage.js` | 15KB | **Authentication** - Login/Register forms |
| `ActivationPage.js` | 10KB | **[REMOVED]** - Was license activation |

### Components Directory (`/frontend/src/components/`)

| File | Purpose |
|------|---------|
| `Layout.js` | **Main Layout** - Sidebar navigation, header, user menu |
| `NetworkDiagnosticsModal.js` | **Diagnostics Popup** - Ping, Traceroute, AI Routing tabs |
| `PendingActionsNotification.js` | **Notification Bell** - Pending AI actions requiring approval |
| `VoiceAlertService.js` | **Voice Alerts** - Text-to-speech for network failures |
| `ui/` | **Shadcn/UI Components** - 46 reusable UI components |

### Services Directory (`/frontend/src/services/`)

| File | Purpose |
|------|---------|
| `api.js` | **API Client** - Axios instance, endpoint definitions for all API calls |
| `auth.js` | **Auth Service** - Token management, getToken(), setToken(), getAuthHeader() |
| `config.js` | **Config Service** - Backend URL management, Electron IPC bridge |

### Context Directory (`/frontend/src/context/`)

| File | Purpose |
|------|---------|
| `AuthContext.js` | **Auth Provider** - User state, login/logout functions, role checking |

---

## Electron Desktop App (`/frontend/electron/`)

| File | Purpose |
|------|---------|
| `main.js` | **Main Process** - Window management, native menus, IPC handlers |
| `preload.js` | **Preload Script** - Context bridge, secure IPC exposure |
| `assets/` | **App Icons** - PNG, ICO, ICNS for all platforms |

---

## Data Flow Diagrams

### Authentication Flow

```
┌──────────┐    POST /api/auth/login    ┌──────────┐    Verify    ┌──────────┐
│  Login   │ ────────────────────────▶  │  FastAPI │ ──────────▶  │ MongoDB  │
│   Page   │                            │  Server  │              │  users   │
└──────────┘                            └──────────┘              └──────────┘
     ▲                                       │
     │           JWT Token                   │
     └───────────────────────────────────────┘
```

### AI Troubleshooting Flow

```
┌──────────┐   Right-click    ┌──────────┐   POST /api/incidents/{id}/ai-troubleshoot
│ Incident │ ──────────────▶  │  Context │ ────────────────────────────────────────▶
│   Row    │                  │   Menu   │
└──────────┘                  └──────────┘
                                                    │
                                                    ▼
┌──────────┐    Response      ┌──────────┐   Call Emergent LLM   ┌──────────┐
│ AI Modal │ ◀────────────────│ server.py│ ◀───────────────────── │ agents.py│
│ Display  │                  │          │                        │   (AI)   │
└──────────┘                  └──────────┘                        └──────────┘
```

### Network Discovery Flow

```
┌──────────────┐   Request Scan   ┌──────────┐   Approve   ┌──────────────┐
│  Discovery   │ ───────────────▶ │  Admin   │ ─────────▶  │   Backend    │
│    Page      │                  │ Approval │             │  Discovery   │
└──────────────┘                  └──────────┘             └──────────────┘
                                                                  │
       ┌──────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────┐                  ┌──────────────┐
│ network_     │   SNMP/Ping/    │   MongoDB    │
│ services.py  │ ─────────────▶  │ devices +    │
│              │   ARP Scan      │ assets       │
└──────────────┘                  └──────────────┘
```

---

## Database Collections

| Collection | Purpose | Key Fields |
|------------|---------|------------|
| `users` | User accounts | email, password_hash, role, name |
| `devices` | Monitored devices | ip_address, type, status, metrics |
| `assets` | Asset inventory | asset_tag, vendor, warranty, location |
| `alerts` | Active alerts | severity, device_id, message, status |
| `incidents` | Incident tickets | title, priority, status, ai_analysis |
| `reports` | Generated reports | type, content, period, format |
| `sla_records` | SLA tracking | response_time, resolution_time, met |
| `escalation_rules` | Escalation config | levels, contacts, thresholds |
| `audit_logs` | Audit trail | action, user, resource, timestamp |
| `config_backups` | Device configs | device_id, config_text, version |
| `email_config` | O365/SMTP settings | tenant_id, credentials |
| `snmp_config` | SNMP settings | community, v3_credentials |
| `aaa_config` | RADIUS/TACACS+ | server, port, secret |
| `backup_config` | Backup schedules | method, target, schedule |
| `custom_dashboards` | User dashboards | layout, widgets |
| `agent_executions` | AI agent runs | incident_id, actions, status |
| `pending_actions` | Actions needing approval | command, risk_level |

---

## Technology Stack

### Backend
- **Framework**: FastAPI (Python 3.11+)
- **Database**: MongoDB with Motor (async driver)
- **Authentication**: JWT (python-jose), bcrypt
- **Network**: pysnmp (SNMP), paramiko (SSH), netaddr (subnets)
- **AAA**: pyrad (RADIUS), tacacs_plus (TACACS+)
- **Reports**: reportlab (PDF generation)
- **AI**: Emergent LLM integration

### Frontend
- **Framework**: React 18 with Create React App
- **Styling**: TailwindCSS, Shadcn/UI
- **State**: React Context API
- **HTTP**: Axios
- **Charts**: Recharts
- **Layout**: react-grid-layout (drag & drop)
- **Routing**: React Router v6

### Desktop
- **Framework**: Electron
- **Platforms**: Windows (NSIS), macOS (DMG), Linux (AppImage/DEB/RPM)

---

## API Endpoints Summary

| Category | Endpoints | Description |
|----------|-----------|-------------|
| Auth | `/api/auth/*` | Login, register, AAA login |
| Devices | `/api/devices/*` | Device CRUD, status |
| Alerts | `/api/alerts/*` | Alert management, AI troubleshoot |
| Incidents | `/api/incidents/*` | Incident CRUD, AI analysis |
| Assets | `/api/assets/*` | Asset inventory CRUD |
| Reports | `/api/reports/*` | Generate, download PDF/CSV |
| Performance | `/api/performance/*` | Metrics collection |
| SLA | `/api/sla/*` | SLA tracking |
| Agents | `/api/agents/*` | AI agent management |
| Escalation | `/api/escalation/*` | Escalation rules |
| Network | `/api/network/*` | Discovery, SNMP, SSH |
| Settings | `/api/settings/*` | All configurations |
| Audit | `/api/audit/*` | Audit logs |
| Backup | `/api/backup/*` | Config backup/restore |
| Users | `/api/users/*` | User management |
| Dashboard | `/api/dashboard/*` | Dashboard layouts |

---

## Key Features by Module

### 1. Monitoring & Alerting
- Real-time device status monitoring
- SNMP polling (v1/v2c/v3)
- Automatic alert generation
- WebSocket real-time updates

### 2. Incident Management
- Incident ticketing system
- AI-powered troubleshooting
- Autonomous resolution (with approval for critical actions)
- Multi-level escalation

### 3. Network Operations
- Interactive 3D topology map
- Network discovery (ARP, Ping, SNMP, Port scan)
- SSH terminal access
- Ping & traceroute diagnostics

### 4. Asset Management
- Complete asset inventory
- Warranty tracking
- Auto-registration from discovery
- OEM/location tracking

### 5. Reporting
- Daily health reports
- Incident summary with RCA
- Device inventory reports
- PDF and CSV export

### 6. Configuration Management
- Multi-vendor config backup (Cisco, Juniper, Arista, etc.)
- Config versioning and diff
- Config restore via SSH

### 7. Security & Compliance
- Role-based access (Admin/Operator)
- AAA authentication (RADIUS/TACACS+)
- 90-day audit logging
- Secure JWT authentication

---

*Last Updated: May 2026*
