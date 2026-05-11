# ATECH NOC Commander - Complete Installation Guide

## Table of Contents
1. [System Requirements](#system-requirements)
2. [Quick Installation](#quick-installation)
3. [Manual Installation](#manual-installation)
4. [Desktop App Installation](#desktop-app-installation)
5. [Configuration](#configuration)
6. [Starting the Application](#starting-the-application)
7. [Troubleshooting](#troubleshooting)

---

## System Requirements

### Minimum Hardware
| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU | 2 cores | 4+ cores |
| RAM | 4 GB | 8+ GB |
| Storage | 2 GB | 10+ GB |
| Network | 100 Mbps | 1 Gbps |

### Supported Operating Systems
- **Windows**: Windows 10, Windows 11, Windows Server 2019/2022
- **macOS**: macOS 10.15 (Catalina) or later
- **Linux**: Ubuntu 20.04+, Debian 11+, RHEL 8+, CentOS 8+, Fedora 35+

### Software Dependencies
| Software | Version | Required |
|----------|---------|----------|
| Python | 3.11+ | Yes |
| MongoDB | 6.0+ | Yes |
| Node.js | 18+ | For Desktop App |

---

## Quick Installation

### Linux/macOS

```bash
# Clone or download the application
cd /path/to/atech-noc-commander

# Make installer executable
chmod +x installer/scripts/install.sh

# Run installer (requires sudo)
./installer/scripts/install.sh
```

### Windows

1. Open **Command Prompt** or **PowerShell** as **Administrator**
2. Navigate to the application directory
3. Run the installer:
```cmd
installer\scripts\install.bat
```

---

## Manual Installation

### Step 1: Install MongoDB

#### Linux (Ubuntu/Debian)
```bash
# Import MongoDB public GPG key
curl -fsSL https://pgp.mongodb.com/server-7.0.asc | sudo gpg -o /usr/share/keyrings/mongodb-server-7.0.gpg --dearmor

# Add repository
echo "deb [ signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg ] https://repo.mongodb.org/apt/ubuntu $(lsb_release -cs)/mongodb-org/7.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-7.0.list

# Install
sudo apt-get update
sudo apt-get install -y mongodb-org

# Start and enable
sudo systemctl start mongod
sudo systemctl enable mongod
```

#### Linux (RHEL/CentOS/Fedora)
```bash
# Add repository
cat <<EOF | sudo tee /etc/yum.repos.d/mongodb-org-7.0.repo
[mongodb-org-7.0]
name=MongoDB Repository
baseurl=https://repo.mongodb.org/yum/redhat/\$releasever/mongodb-org/7.0/x86_64/
gpgcheck=1
enabled=1
gpgkey=https://pgp.mongodb.com/server-7.0.asc
EOF

# Install
sudo dnf install -y mongodb-org

# Start and enable
sudo systemctl start mongod
sudo systemctl enable mongod
```

#### macOS
```bash
# Install Homebrew if not installed
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install MongoDB
brew tap mongodb/brew
brew install mongodb-community@7.0

# Start service
brew services start mongodb-community@7.0
```

#### Windows
1. Download MongoDB Community Server from: https://www.mongodb.com/try/download/community
2. Run the installer (MSI package)
3. Choose "Complete" installation
4. Check "Install MongoDB as a Service"
5. Complete installation

### Step 2: Install Python

#### Linux
```bash
# Ubuntu/Debian
sudo apt-get install -y python3 python3-pip python3-venv

# RHEL/CentOS/Fedora
sudo dnf install -y python3 python3-pip
```

#### macOS
```bash
brew install python@3.11
```

#### Windows
1. Download Python 3.11+ from: https://www.python.org/downloads/
2. **Important**: Check "Add Python to PATH" during installation
3. Complete installation

### Step 3: Setup Python Environment

```bash
# Navigate to backend directory
cd /path/to/atech-noc-commander/backend

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
# Linux/macOS:
source venv/bin/activate
# Windows:
venv\Scripts\activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt

# Install Emergent Integrations (for AI features)
pip install emergentintegrations --extra-index-url https://d33sy5i8bnduwe.cloudfront.net/simple/
```

### Step 4: Configure Environment

```bash
# Copy example environment file
cp backend/.env.example backend/.env

# Edit with your settings
nano backend/.env  # or use your preferred editor
```

Key settings to configure:
```env
MONGO_URL=mongodb://localhost:27017
DB_NAME=atech_noc
JWT_SECRET_KEY=your-secure-random-key
```

### Step 5: Create Admin User

```bash
cd backend
source venv/bin/activate  # Windows: venv\Scripts\activate

python3 << 'EOF'
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from passlib.context import CryptContext
from datetime import datetime, timezone
import uuid

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def create_admin():
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client["atech_noc"]
    
    existing = await db.users.find_one({"email": "admin@noc.com"})
    if existing:
        print("Admin user already exists")
        return
    
    admin = {
        "id": str(uuid.uuid4()),
        "email": "admin@noc.com",
        "name": "Admin User",
        "password_hash": pwd_context.hash("admin123"),
        "role": "admin",
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.users.insert_one(admin)
    print("Admin user created!")
    print("Email: admin@noc.com")
    print("Password: admin123")

asyncio.run(create_admin())
EOF
```

---

## Desktop App Installation

### Building Desktop Installers

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
yarn install

# Build for your platform
yarn electron:build:win    # Windows
yarn electron:build:mac    # macOS
yarn electron:build:linux  # Linux
yarn electron:build:all    # All platforms
```

### Installing Pre-built Desktop App

1. Download the installer for your platform from releases
2. Run the installer:
   - **Windows**: Run `ATECH NOC Commander-x.x.x-win-x64.exe`
   - **macOS**: Open `ATECH NOC Commander-x.x.x-mac-x64.dmg` and drag to Applications
   - **Linux**: Run `ATECH NOC Commander-x.x.x-linux.AppImage` or install `.deb`/`.rpm`

---

## Configuration

### Backend Configuration (`backend/.env`)

```env
# Database
MONGO_URL=mongodb://localhost:27017
DB_NAME=atech_noc

# Authentication
JWT_SECRET_KEY=generate-a-secure-random-key
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Server
HOST=0.0.0.0
PORT=8001

# AI Features (Optional)
EMERGENT_LLM_KEY=your-emergent-key

# Email (Optional - for SOS alerts)
O365_TENANT_ID=your-tenant-id
O365_CLIENT_ID=your-client-id
O365_CLIENT_SECRET=your-secret
```

### Frontend Configuration (`frontend/.env`)

```env
REACT_APP_BACKEND_URL=http://localhost:8001
```

---

## Starting the Application

### Using Start Scripts

```bash
# Linux/macOS
./start.sh

# Windows
start.bat
```

### Manual Start

```bash
# Terminal 1: Start Backend
cd backend
source venv/bin/activate
python -m uvicorn server:app --host 0.0.0.0 --port 8001

# Terminal 2: Serve Frontend (if not using desktop app)
cd frontend/build
python3 -m http.server 3000
```

### Access the Application

- **Web UI**: http://localhost:3000
- **API**: http://localhost:8001
- **API Docs**: http://localhost:8001/docs

### Default Credentials

| Field | Value |
|-------|-------|
| Email | admin@noc.com |
| Password | admin123 |

**⚠️ Important**: Change the default password after first login!

---

## Troubleshooting

### MongoDB Connection Failed

```bash
# Check if MongoDB is running
sudo systemctl status mongod  # Linux
brew services list | grep mongo  # macOS

# Start MongoDB
sudo systemctl start mongod  # Linux
brew services start mongodb-community@7.0  # macOS
net start MongoDB  # Windows (Admin CMD)
```

### Python Dependencies Error

```bash
# Ensure virtual environment is activated
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate  # Windows

# Reinstall dependencies
pip install --upgrade pip
pip install -r requirements.txt --force-reinstall
```

### Port Already in Use

```bash
# Find process using port 8001
lsof -i :8001  # Linux/macOS
netstat -ano | findstr :8001  # Windows

# Kill the process
kill -9 <PID>  # Linux/macOS
taskkill /PID <PID> /F  # Windows
```

### Frontend Not Loading

1. Ensure backend is running on port 8001
2. Check `frontend/.env` has correct `REACT_APP_BACKEND_URL`
3. Clear browser cache and reload
4. Check browser console for errors

### SNMP Discovery Not Working

1. Ensure target devices have SNMP enabled
2. Verify SNMP community strings in Settings
3. Check firewall allows UDP port 161
4. Test with: `snmpwalk -v2c -c public <device-ip> system`

### AI Features Not Working

1. Verify `EMERGENT_LLM_KEY` is set in backend/.env
2. Check API key has sufficient balance
3. Review backend logs for AI-related errors

---

## Support

For additional support:
- Check the USER_GUIDE.md for feature documentation
- Review ARCHITECTURE.md for technical details
- Contact Ameya Technology support

---

*Last Updated: May 2026*
