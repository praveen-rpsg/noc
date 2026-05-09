# ATECH NOC Commander - User Guide

## Table of Contents
1. [Introduction](#introduction)
2. [Getting Started](#getting-started)
3. [Dashboard](#dashboard)
4. [Dashboard Editor](#dashboard-editor)
5. [Monitoring](#monitoring)
6. [Network Topology](#network-topology)
7. [Network Discovery](#network-discovery)
8. [Configuration Backup](#configuration-backup)
9. [Alerts Management](#alerts-management)
10. [Incident Management](#incident-management)
11. [AI-Powered Features](#ai-powered-features)
12. [Performance Monitoring](#performance-monitoring)
13. [Asset Management](#asset-management)
14. [SSH Terminal](#ssh-terminal)
15. [AI Agents](#ai-agents)
16. [Escalation Management](#escalation-management)
17. [Reports](#reports)
18. [Configuration](#configuration)
19. [SLA Management](#sla-management)
20. [User Management](#user-management)
21. [Audit Logs](#audit-logs)
22. [Settings](#settings)
23. [Desktop Application](#desktop-application)
24. [Troubleshooting](#troubleshooting)

---

## Introduction

**ATECH NOC Commander** is an AI-powered Network Operation Center (NOC) tool developed by Ameya Technology. It provides comprehensive 24x7 monitoring, intelligent incident management, and autonomous troubleshooting capabilities for enterprise networks.

### Key Features
- Real-time network monitoring and alerting
- AI-powered autonomous incident resolution
- Multi-vendor device support (Cisco, Juniper, Arista, Huawei, Palo Alto, Fortinet, F5)
- Interactive 3D network topology
- Voice alerts for critical failures
- Configuration backup and restore
- RADIUS/TACACS+ authentication integration
- Comprehensive audit logging
- Desktop application for Windows, macOS, and Linux

### User Roles
| Role | Access Level |
|------|-------------|
| **Administrator** | Full system access including user management, license management, audit logs, and all settings |
| **Operator** | Operational access to monitoring, incidents, alerts, and device management |

---

## Getting Started

### First-Time Activation

1. **Launch the Application**
   - Open the ATECH NOC Commander application (web or desktop)
   - You will see the **Activation Page**

2. **Enter Activation Code**
   - Enter your activation code in the format: `ATECH-XXXX-XXXX-XXXX`
   - Click **Activate**
   - Activation is permanent and tied to your installation

3. **Login**
   - After activation, you'll see the login page
   - Enter your email and password
   - Click **Sign In**

### Default Credentials
For initial setup, use the default admin account:
- **Email**: admin@noc.com
- **Password**: admin123

> **Important**: Change the default password immediately after first login!

### Desktop Application - Server Configuration

If using the desktop application:
1. Click **Server Settings** on the login page
2. Enter your backend server URL (e.g., `https://your-server.com`)
3. Click **Test Connection** to verify
4. Click **Save** and proceed to login

---

## Dashboard

The Dashboard provides a comprehensive overview of your network infrastructure.

### Key Performance Indicators (KPIs)
- **Total Devices**: Number of monitored devices
- **Active Alerts**: Current unresolved alerts
- **Open Incidents**: Active incident tickets
- **Device Uptime**: Average network availability

### Dashboard Widgets
- **Device Status Distribution**: Pie chart showing online/offline/degraded devices
- **Alert Trends**: Line chart showing alert volume over time
- **Recent Alerts**: List of latest alerts with severity indicators
- **Recent Incidents**: Latest incident tickets
- **SLA Compliance**: Service level agreement status
- **Performance Metrics**: CPU, memory, and bandwidth utilization

### Navigation
Use the sidebar to navigate between different modules:
- Click any menu item to navigate
- Collapse/expand sidebar using the menu button
- The notification bell shows pending AI actions requiring approval

---

## Dashboard Editor

Customize your dashboard layout with drag-and-drop widgets.

### Accessing the Editor
1. Navigate to **Dashboard Editor** from the sidebar
2. Click **Edit Mode** to enable editing

### Available Widgets
| Widget | Description |
|--------|-------------|
| Device Status | Shows device online/offline counts |
| Active Alerts | Chart of alert distribution by severity |
| Incident Trends | Line chart of incident volume |
| Topology Mini-Map | Small network topology view |
| Performance Metrics | CPU/Memory/Bandwidth gauges |
| Recent Activity | Latest system events |
| SLA Compliance | SLA status overview |
| Custom Metric | Configurable metric display |

### Editing Dashboard
1. **Add Widget**: Click **Add Widget**, select type, and click **Add**
2. **Move Widget**: Drag widgets by their header to reposition
3. **Resize Widget**: Drag widget edges to resize
4. **Remove Widget**: Click the **X** button on a widget
5. **Save Layout**: Click **Save Layout** to persist changes

### Global Layouts (Admin Only)
- Toggle **Apply to All Users** to make your layout the default for all users
- Users can override with personal layouts

---

## Monitoring

Real-time monitoring of all network devices.

### Device List
- View all devices with status indicators (green = online, red = offline, amber = degraded)
- Search and filter devices by name, type, location, or status
- Click a device to view detailed information

### Device Details
Tabbed interface showing:

**General Tab**
- IP Address, MAC Address, Hostname
- Location, Vendor, Model
- Serial Number, Description

**Network Tab**
- CPU Usage (progress bar)
- Memory Usage (progress bar)
- Uptime in hours
- AAA Authentication status (purple badge if enabled)

**System Tab**
- OS Version (with outdated warning if >1 year)
- OS Install Date
- Firmware Version
- Warranty Status (Active/Expired/Expiring Soon)

### Device Actions
- **Edit**: Modify device properties
- **Delete**: Remove device from monitoring
- **SSH Connect**: Open terminal session
- **Run Diagnostics**: Ping and traceroute

---

## Network Topology

Interactive 3D visualization of your network infrastructure.

### Navigation
- **Pan**: Click and drag to move the view
- **Zoom**: Scroll wheel or pinch gesture
- **Rotate**: Right-click and drag (3D mode)
- **Select Device**: Click on a device node

### Features
- **Device Icons**: 3D icons represent device types (routers, switches, firewalls, servers)
- **Connection Lines**: Show network links between devices
- **Status Colors**: Green (online), Red (offline), Amber (degraded)
- **Drag Nodes**: Reposition devices for better visualization

### Traceroute Path Display
When viewing traceroute results:
1. Click **Show Path on Network Topology** in diagnostics
2. The path is highlighted on the topology map
3. A banner shows the target and hop count
4. Click **Clear Path** to dismiss

---

## Network Discovery

Automatically discover devices on your network.

### Discovery Methods
| Method | Description |
|--------|-------------|
| ARP Scan | Layer 2 discovery using ARP protocol |
| Ping Sweep | ICMP-based host discovery |
| SNMP Discovery | Discover SNMP-enabled devices with detailed info |
| Port Scan | TCP port scanning for service detection |

### Running a Discovery
1. Navigate to **Network Discovery**
2. Select a **Subnet** from the dropdown (auto-detected)
3. Choose **Discovery Methods** to use
4. Click **Request Discovery**
5. Wait for admin approval (if required)

### Approval Workflow (Admin)
1. View pending requests in **Pending Approvals** section
2. Review request details (user, subnet, methods)
3. Click **Approve** to execute or **Reject** to deny

### Results
- Discovered devices are automatically added to the device inventory
- View discovery history with status and device counts
- Export results for documentation

---

## Configuration Backup

Backup and restore device configurations with multi-vendor support.

### Supported Vendors
- Cisco (IOS, IOS-XE, NX-OS, ASA)
- Juniper (Junos)
- Arista (EOS)
- Huawei (VRP)
- Palo Alto (PAN-OS)
- Fortinet (FortiOS)
- F5 (BIG-IP TMOS)

### Creating a Backup
1. Navigate to **Config Backup**
2. Select a device from the **Network Devices** list
3. Click **Create Backup**
4. Enter SSH credentials when prompted
5. Backup is created with automatic versioning

### Viewing Current Configuration
1. Select a device
2. Click **View Current**
3. Enter SSH credentials
4. View live configuration from the device
5. Optionally click **Save as Backup**

### Restoring Configuration
1. Select a backup from the history
2. Click the **Restore** button (upload icon)
3. Confirm the restore operation
4. Enter SSH credentials
5. Configuration is pushed to the device

### Comparing Configurations
1. Click **View** on a backup to open it
2. Select another version from **Compare with...** dropdown
3. Click **Compare** to see differences
4. Additions shown in green, deletions in red

---

## Alerts Management

Monitor and manage network alerts.

### Alert Severity Levels
| Severity | Color | Description |
|----------|-------|-------------|
| Critical | Red | Immediate attention required |
| High | Orange | Urgent issue |
| Medium | Yellow | Important but not urgent |
| Low | Blue | Informational |

### Alert Actions
- **Acknowledge**: Mark alert as seen
- **Resolve**: Close the alert
- **Create Incident**: Escalate to incident ticket
- **AI Troubleshoot**: Get AI analysis (right-click menu)

### Right-Click Context Menu
Right-click on any alert row for:
- **AI Troubleshoot**: Detailed AI analysis and recommendations
- **Network Diagnostics**: Run ping and traceroute
- **View Details**: See full alert information

### Voice Alerts
Configure voice announcements for critical alerts:
1. Click the **speaker icon** in the header
2. Enable/disable voice alerts
3. Select voice type (male/female)
4. Adjust volume and speech rate
5. Click **Test** to preview

---

## Incident Management

Track and manage incident tickets.

### Incident Lifecycle
1. **New**: Incident created
2. **Investigating**: Under analysis
3. **In Progress**: Being resolved
4. **Resolved**: Issue fixed
5. **Closed**: Ticket closed

### Creating Incidents
- Manually: Click **Create Incident** button
- From Alert: Click **Create Incident** in alert actions
- Automatically: AI agent can create from alerts

### Incident Actions
- **Edit**: Update incident details
- **Assign**: Assign to team member
- **Escalate**: Move to higher priority
- **Resolve**: Mark as resolved
- **Run AI Agent**: Autonomous resolution (right-click)

### Right-Click Context Menu
Right-click on any incident row for:
- **Run AI Agent (Auto-Fix)**: Autonomous resolution
- **AI Troubleshoot**: Detailed analysis report
- **Network Diagnostics**: Ping and traceroute
- **View Details**: Full incident information

---

## AI-Powered Features

### AI Troubleshooting

Get detailed AI analysis for incidents and alerts:

1. Right-click on an incident or alert
2. Select **AI Troubleshoot**
3. View the comprehensive report:
   - **Summary**: Quick overview
   - **Root Cause Analysis**: Probable causes
   - **Troubleshooting Steps**: Step-by-step commands
   - **Recommended Actions**: Resolution suggestions
   - **Prevention Measures**: Future prevention tips
   - **Escalation Recommendation**: When to escalate

### Autonomous AI Agent

The AI Agent can automatically resolve incidents:

**Auto-Resolve Actions** (No confirmation needed):
- Configuration corrections
- Log clearing
- Route table fixes
- Traceroute analysis
- STP loop detection
- Asymmetric routing detection
- Memory cleanup
- Service restarts
- Interface bounce

**Actions Requiring Confirmation**:
- Device reboot
- Link/Interface reset
- Firmware update
- Factory reset
- Power cycle
- Hardware replacement

### Pending Actions
1. Click the **notification bell** in the header
2. View pending actions requiring approval
3. Review details: command, risk level, estimated downtime
4. Click **Approve** or **Reject**

### Network Diagnostics

Run diagnostics from any incident or alert:

**Ping Status Tab**:
- Packet count, loss percentage
- Average latency, min/max range
- Individual ping results
- Auto-refresh option (5 seconds)

**Traceroute Map Tab**:
- Visual hop-by-hop path
- Latency at each hop
- Path quality indicator
- Issues detection (high latency, timeouts)
- **Show Path on Network Topology** button

**Routing AI Tab**:
- AI-powered routing optimization
- Protocol recommendations (OSPF, EIGRP, BGP, IS-IS)
- Implementation priority with impact levels
- Configuration suggestions

---

## Performance Monitoring

Track performance metrics across your infrastructure.

### Metrics Collected
- CPU Utilization
- Memory Usage
- Network Bandwidth (In/Out)
- Disk I/O
- Response Time

### Performance Charts
- Line charts showing trends over time
- Selectable time ranges (1h, 6h, 24h, 7d, 30d)
- Device comparison views
- Threshold indicators

### Alerts on Thresholds
Configure alerts when metrics exceed thresholds:
- CPU > 90%
- Memory > 85%
- Bandwidth > 80%
- Response Time > 500ms

---

## Asset Management

Maintain comprehensive asset inventory.

### Asset Information
- Device details (vendor, model, serial)
- Warranty status and expiry dates
- Location and rack position
- Purchase date and cost
- Maintenance contracts

### Asset Actions
- **Add Asset**: Register new asset
- **Edit**: Update asset information
- **Delete**: Remove from inventory
- **Export**: Download asset list

### Warranty Tracking
- **Active** (Green): Warranty valid
- **Expiring Soon** (Amber): Within 90 days
- **Expired** (Red): Warranty ended

---

## SSH Terminal

Connect to devices via SSH for command-line access.

### Connecting
1. Navigate to **SSH Terminal**
2. Select a device from the dropdown
3. Enter SSH credentials:
   - Username
   - Password
   - Port (default: 22)
4. Click **Connect**

### Terminal Features
- Full terminal emulation
- Command history (up/down arrows)
- Copy/paste support
- Session logging
- Multi-tab sessions

### Disconnecting
- Click **Disconnect** button
- Or close the terminal tab
- Sessions auto-close after idle timeout

---

## AI Agents

Manage and configure AI automation agents.

### Agent Types
| Agent | Purpose |
|-------|---------|
| Incident Resolver | Automatically resolve incidents |
| Alert Analyzer | Analyze and categorize alerts |
| Performance Optimizer | Optimize network performance |
| Security Monitor | Monitor for security threats |

### Agent Configuration
1. Navigate to **AI Agents**
2. View available agents and their status
3. Click **Configure** to adjust settings:
   - Enable/disable agent
   - Set auto-trigger conditions
   - Configure action thresholds
   - Set notification preferences

### Execution History
- View past agent executions
- See actions taken and results
- Review any errors or failures

---

## Escalation Management

Configure escalation policies and contacts.

### Escalation Levels
| Level | Typical Contacts |
|-------|-----------------|
| L1 | NOC Operators |
| L2 | Network Engineers |
| L3 | Senior Engineers |
| L4 | Management |

### Adding Contacts
1. Navigate to **Escalation**
2. Click **Add Contact**
3. Enter:
   - Name
   - Email
   - Phone
   - Escalation Level
   - Active hours
4. Click **Save**

### Escalation Rules
Configure automatic escalation:
- Time-based: Escalate if not resolved in X hours
- Severity-based: Auto-escalate critical alerts
- Device-based: Special handling for critical infrastructure

### SOS Alerts
Hardware failures automatically trigger SOS alerts:
- Email sent to ALL escalation contacts
- Voice alerts if enabled
- High-priority incident created

---

## Reports

Generate and download reports.

### Report Types
- Incident Summary
- Alert Analysis
- Performance Metrics
- SLA Compliance
- Asset Inventory
- Audit Log

### Generating Reports
1. Navigate to **Reports**
2. Select report type
3. Choose date range
4. Select filters (devices, severity, etc.)
5. Click **Generate**

### Download Options
- **PDF**: Formatted report with ATECH branding
- **CSV**: Raw data for spreadsheet analysis

### Scheduling Reports
Configure automatic report generation:
1. Click **Schedule** on a report
2. Set frequency (daily, weekly, monthly)
3. Add email recipients
4. Click **Save Schedule**

---

## Configuration

Manage device configurations.

### Configuration Templates
Create reusable configuration templates:
1. Navigate to **Configuration**
2. Click **Create Template**
3. Enter template name and content
4. Use variables: `{{device_name}}`, `{{ip_address}}`
5. Save template

### Applying Configurations
1. Select a template
2. Choose target device(s)
3. Preview the configuration
4. Click **Apply**
5. Review results

### Configuration Compliance
- Compare device configs against templates
- Identify configuration drift
- Generate compliance reports

---

## SLA Management

Track and manage Service Level Agreements.

### SLA Metrics
- Uptime percentage
- Response time
- Resolution time
- Escalation compliance

### SLA Dashboard
- Overall SLA compliance score
- Trending chart
- At-risk services
- SLA breach history

### Creating SLA
1. Navigate to **SLA Management**
2. Click **Create SLA**
3. Define:
   - Name and description
   - Target metrics
   - Business hours
   - Penalty conditions
4. Assign to services/devices
5. Click **Save**

---

## User Management

*Admin only*

Manage user accounts and roles.

### Viewing Users
1. Navigate to **User Management**
2. See all users with:
   - Name and email
   - Role (Admin/Operator)
   - Status (Active/Disabled)
   - Last login

### Creating Users
1. Click **Add User**
2. Enter:
   - Name
   - Email
   - Role (Admin or Operator)
   - Password
3. Click **Create**

### User Actions
- **Edit**: Update user details
- **Reset Password**: Set new password
- **Enable/Disable**: Toggle account status
- **Delete**: Remove user account

### Role Permissions
| Permission | Admin | Operator |
|------------|-------|----------|
| View Dashboard | Yes | Yes |
| Manage Incidents | Yes | Yes |
| Manage Alerts | Yes | Yes |
| Manage Devices | Yes | Yes |
| Manage Users | Yes | No |
| Manage Licenses | Yes | No |
| View Audit Logs | Yes | No |
| System Settings | Yes | Limited |

---

## Audit Logs

*Admin only*

Track all user and system actions for compliance.

### Accessing Audit Logs
1. Navigate to **Audit Logs**
2. View summary statistics:
   - Total Logs
   - Today's Actions
   - Failed Actions
   - Retention Period (90 days)

### Filtering Logs
- **Action Type**: Login, CRUD operations, config changes
- **User Email**: Search by user
- **Resource Type**: Device, user, incident, etc.
- **Date Range**: Start and end dates

### Log Details
Click **View** on any log entry to see:
- Timestamp
- Action type
- User information
- Resource details
- Success/failure status
- Additional metadata (JSON)

### Exporting Logs
- Click **Export CSV** for spreadsheet format
- Click **Export JSON** for programmatic use
- Logs include all filtered results

### Log Retention
- Logs are automatically deleted after 90 days
- Click **Cleanup** to manually remove old logs

---

## Settings

Configure system-wide settings.

### Connection (Desktop Only)
- Backend server URL
- Test connection
- Save settings

### License
*Admin only*
- Generate activation codes
- View code statistics
- Manage existing codes
- Revoke unused codes

### Email
Configure email notifications:

**Microsoft Graph API** (Recommended):
- Tenant ID
- Client ID
- Client Secret
- Sender Email
- Test connection

**SMTP Fallback**:
- SMTP Server
- Port
- Username/Password
- TLS encryption

### SNMP
Configure SNMP monitoring:

**v1/v2c**:
- Community string
- Read/Write access

**v3**:
- Security level
- Auth/Privacy protocols
- Credentials

### OpenStack
Connect to OpenStack cloud:
- Auth URL
- Project name
- Credentials
- Region
- Services to monitor

### Oracle
Connect to Oracle Database:
- Host and port
- SID/Service name
- Credentials
- Metrics to collect

### vCenter
Connect to VMware vCenter:
- Server address
- Credentials
- SSL verification
- Monitoring options

### AAA
Configure RADIUS/TACACS+:
- Server type (RADIUS/TACACS+)
- Primary server (host, port)
- Secondary server (backup)
- Shared secret
- Timeout and retries
- **Test Connection** to verify

### Backup
Configure backup schedules:
- Backup method (TFTP, SCP, SSH, API)
- Target server
- Schedule (daily, weekly, monthly)
- Retention policy
- Manual trigger

---

## Desktop Application

ATECH NOC Commander is available as a desktop application.

### Supported Platforms
- **Windows**: 10, 11 (x64, x86)
- **macOS**: 10.15+ (Intel, Apple Silicon)
- **Linux**: Ubuntu, Fedora, RHEL (x64)

### Installation

**Windows**:
1. Download `ATECH-NOC-Commander-Setup.exe`
2. Run the installer
3. Follow the installation wizard
4. Launch from Start Menu

**macOS**:
1. Download `ATECH-NOC-Commander.dmg`
2. Open the DMG file
3. Drag app to Applications folder
4. Launch from Applications

**Linux**:
1. Download `.AppImage`, `.deb`, or `.rpm`
2. Install using your package manager:
   - `sudo dpkg -i atech-noc-commander.deb`
   - `sudo rpm -i atech-noc-commander.rpm`
3. Or run AppImage directly: `./ATECH-NOC-Commander.AppImage`

### First-Time Setup
1. Launch the application
2. Click **Server Settings**
3. Enter your backend server URL
4. Test and save the connection
5. Proceed with activation and login

### Menu Bar
- **File**: Exit application
- **View**: Zoom, toggle developer tools
- **NOC Tools**: Quick access to features
- **Help**: About, documentation

### Keyboard Shortcuts
| Action | Windows/Linux | macOS |
|--------|--------------|-------|
| Refresh | Ctrl+R | Cmd+R |
| Zoom In | Ctrl++ | Cmd++ |
| Zoom Out | Ctrl+- | Cmd+- |
| Reset Zoom | Ctrl+0 | Cmd+0 |
| Dev Tools | Ctrl+Shift+I | Cmd+Option+I |

---

## Troubleshooting

### Common Issues

**Cannot Login**
- Verify email and password
- Check if account is disabled
- Ensure backend server is reachable
- Clear browser cache and cookies

**No Data on Dashboard**
- Check device connectivity
- Verify SNMP configuration
- Ensure polling is enabled
- Check time synchronization

**Voice Alerts Not Working**
- Enable voice alerts in settings
- Check browser audio permissions
- Select a valid voice from the list
- Test with the Test button

**SSH Connection Failed**
- Verify IP address is correct
- Check SSH port (default 22)
- Confirm credentials
- Ensure device allows SSH access

**Config Backup Failed**
- Check device is reachable
- Verify SSH credentials
- Confirm user has sufficient privileges
- Check device supports SSH

**AAA Authentication Failed**
- Test RADIUS/TACACS+ server connectivity
- Verify shared secret is correct
- Check server is configured for the user
- Review AAA server logs

### Getting Help
- Check documentation at [/DEPLOYMENT_GUIDE.md](/DEPLOYMENT_GUIDE.md)
- Review API documentation
- Contact Ameya Technology support

---

## Appendix

### Supported Device Types
| Type | Icon | Examples |
|------|------|----------|
| Router | Network | Cisco ASR, Juniper MX |
| Switch | Layers | Catalyst, Arista |
| Firewall | Shield | Palo Alto, Fortinet |
| Server | Server | Dell, HP |
| Load Balancer | Scale | F5, Citrix |
| Access Point | Wifi | Aruba, Cisco |
| Cloud Instance | Cloud | AWS, Azure, GCP |

### API Reference
Base URL: `https://your-server/api`

Authentication: Bearer token in Authorization header

Key Endpoints:
- `/auth/login` - User authentication
- `/devices` - Device CRUD
- `/alerts` - Alert management
- `/incidents` - Incident management
- `/dashboard/stats` - Dashboard metrics
- `/settings/*` - Configuration

### Glossary
| Term | Definition |
|------|------------|
| NOC | Network Operation Center |
| SLA | Service Level Agreement |
| SNMP | Simple Network Management Protocol |
| AAA | Authentication, Authorization, Accounting |
| RADIUS | Remote Authentication Dial-In User Service |
| TACACS+ | Terminal Access Controller Access-Control System Plus |

---

*Document Version: 1.0*
*Last Updated: May 2026*
*ATECH NOC Commander by Ameya Technology*
