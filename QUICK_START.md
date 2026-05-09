# ATECH NOC Commander - Quick Start Guide

## Welcome to ATECH NOC Commander!

This quick start guide will help you get up and running in 5 minutes.

---

## Step 1: Activate Your Application

1. Open ATECH NOC Commander
2. Enter your activation code: `ATECH-XXXX-XXXX-XXXX`
3. Click **Activate**

> Don't have a code? Contact your administrator.

---

## Step 2: Login

**Default Admin Credentials:**
- Email: `admin@noc.com`
- Password: `admin123`

> **Important:** Change your password immediately after first login!

---

## Step 3: Explore the Dashboard

After login, you'll see your network overview:

| Widget | What It Shows |
|--------|--------------|
| Device Status | Online/Offline devices |
| Active Alerts | Current alerts by severity |
| Open Incidents | Incident tickets |
| SLA Compliance | Service level status |

---

## Step 4: Add Your First Device

1. Go to **Monitoring** in the sidebar
2. Click **Add Device**
3. Fill in:
   - Name: `My Router`
   - IP Address: `192.168.1.1`
   - Type: `Router`
   - Vendor: `Cisco`
4. Click **Save**

---

## Step 5: Configure SNMP Monitoring

1. Go to **Settings** → **SNMP** tab
2. Add community string:
   - Community: `public`
   - Version: `v2c`
3. Click **Save**

Now your devices will be polled every 30 seconds!

---

## Step 6: Set Up Email Alerts

1. Go to **Settings** → **Email** tab
2. Choose **Microsoft Graph API** (recommended)
3. Enter your Azure AD credentials:
   - Tenant ID
   - Client ID
   - Client Secret
   - Sender Email
4. Click **Test** then **Save**

---

## Step 7: Configure Escalation Contacts

1. Go to **Escalation** in the sidebar
2. Click **Add Contact**
3. Enter contact details:
   - Name
   - Email
   - Phone
   - Escalation Level (L1-L4)
4. Click **Save**

Now critical alerts will notify your team!

---

## Key Features to Try

### AI Troubleshooting
- Right-click any incident or alert
- Select **AI Troubleshoot**
- Get detailed analysis and recommendations

### Network Diagnostics
- Right-click any device-related item
- Select **Network Diagnostics**
- Run ping and traceroute tests

### Config Backup
- Go to **Config Backup**
- Select a network device
- Click **Create Backup**
- Your configs are now safely stored!

### Voice Alerts
- Click the speaker icon in the header
- Enable voice alerts
- Get audio notifications for critical events

---

## Need Help?

- **Full Documentation**: [USER_GUIDE.md](/USER_GUIDE.md)
- **Deployment Guide**: [DEPLOYMENT_GUIDE.md](/DEPLOYMENT_GUIDE.md)
- **Support**: Contact Ameya Technology

---

## Keyboard Shortcuts

| Action | Shortcut |
|--------|----------|
| Search | Ctrl/Cmd + K |
| Refresh | Ctrl/Cmd + R |
| Help | F1 |

---

**You're all set! Enjoy ATECH NOC Commander.**

*Ameya Technology - AI-Powered Network Operations*
