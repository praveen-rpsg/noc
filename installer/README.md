# ATECH NOC Commander - Standalone Installation Package

## Package Structure
```
atech-noc-commander/
├── backend/                    # Python FastAPI application
├── frontend/                   # React application (pre-built)
├── mongodb/                    # MongoDB data directory
├── installer/
│   ├── scripts/
│   │   ├── install.sh          # Linux/macOS installer
│   │   ├── install.bat         # Windows installer
│   │   ├── start.sh            # Linux/macOS start script
│   │   ├── start.bat           # Windows start script
│   │   ├── stop.sh             # Linux/macOS stop script
│   │   └── stop.bat            # Windows stop script
│   └── config/
│       ├── mongodb.conf        # MongoDB configuration
│       └── supervisor.conf     # Process supervisor config
├── requirements.txt            # Python dependencies
├── package.json               # Node.js dependencies
└── README.md                  # Installation guide
```

## System Requirements

### Minimum Requirements
- **OS**: Windows 10/11, macOS 10.15+, Ubuntu 20.04+
- **RAM**: 4GB (8GB recommended)
- **Storage**: 2GB free space
- **CPU**: 2 cores (4 cores recommended)

### Software Requirements (Auto-installed)
- Python 3.11+
- Node.js 18+ (for desktop app only)
- MongoDB 6.0+

## Quick Installation

### Linux/macOS
```bash
chmod +x installer/scripts/install.sh
./installer/scripts/install.sh
```

### Windows
```cmd
installer\scripts\install.bat
```

## Manual Installation

### Step 1: Install MongoDB
- Download from https://www.mongodb.com/try/download/community
- Install and start MongoDB service

### Step 2: Install Python Dependencies
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Step 3: Configure Environment
```bash
cp backend/.env.example backend/.env
# Edit .env with your MongoDB connection string
```

### Step 4: Start Application
```bash
# Start backend
cd backend
python -m uvicorn server:app --host 0.0.0.0 --port 8001

# In another terminal, serve frontend
cd frontend/build
python -m http.server 3000
```

## Default Credentials
- **Email**: admin@noc.com
- **Password**: admin123

## Ports Used
- **Backend API**: 8001
- **Frontend**: 3000
- **MongoDB**: 27017
