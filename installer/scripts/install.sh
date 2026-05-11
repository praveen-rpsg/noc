#!/bin/bash
# ATECH NOC Commander - Linux/macOS Installation Script
# This script installs all dependencies and sets up the application

set -e

echo "=========================================="
echo "  ATECH NOC COMMANDER - INSTALLER"
echo "  AI-Powered Network Operation Center"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
APP_DIR="$( cd "$SCRIPT_DIR/../.." && pwd )"

echo -e "${YELLOW}Installation directory: $APP_DIR${NC}"
echo ""

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to print status
print_status() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

# Detect OS
detect_os() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        OS="linux"
        if command_exists apt-get; then
            PKG_MANAGER="apt"
        elif command_exists yum; then
            PKG_MANAGER="yum"
        elif command_exists dnf; then
            PKG_MANAGER="dnf"
        fi
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        OS="macos"
        PKG_MANAGER="brew"
    else
        print_error "Unsupported operating system: $OSTYPE"
        exit 1
    fi
    print_status "Detected OS: $OS (Package manager: $PKG_MANAGER)"
}

# Install Python
install_python() {
    if command_exists python3; then
        PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2)
        print_status "Python already installed: $PYTHON_VERSION"
    else
        echo "Installing Python 3..."
        if [[ "$PKG_MANAGER" == "apt" ]]; then
            sudo apt-get update
            sudo apt-get install -y python3 python3-pip python3-venv
        elif [[ "$PKG_MANAGER" == "yum" ]] || [[ "$PKG_MANAGER" == "dnf" ]]; then
            sudo $PKG_MANAGER install -y python3 python3-pip
        elif [[ "$PKG_MANAGER" == "brew" ]]; then
            brew install python@3.11
        fi
        print_status "Python installed successfully"
    fi
}

# Install MongoDB
install_mongodb() {
    if command_exists mongod; then
        print_status "MongoDB already installed"
    else
        echo "Installing MongoDB..."
        if [[ "$PKG_MANAGER" == "apt" ]]; then
            # Import MongoDB public GPG key
            curl -fsSL https://pgp.mongodb.com/server-7.0.asc | sudo gpg -o /usr/share/keyrings/mongodb-server-7.0.gpg --dearmor
            echo "deb [ signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg ] https://repo.mongodb.org/apt/ubuntu $(lsb_release -cs)/mongodb-org/7.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-7.0.list
            sudo apt-get update
            sudo apt-get install -y mongodb-org
        elif [[ "$PKG_MANAGER" == "yum" ]] || [[ "$PKG_MANAGER" == "dnf" ]]; then
            cat <<EOF | sudo tee /etc/yum.repos.d/mongodb-org-7.0.repo
[mongodb-org-7.0]
name=MongoDB Repository
baseurl=https://repo.mongodb.org/yum/redhat/\$releasever/mongodb-org/7.0/x86_64/
gpgcheck=1
enabled=1
gpgkey=https://pgp.mongodb.com/server-7.0.asc
EOF
            sudo $PKG_MANAGER install -y mongodb-org
        elif [[ "$PKG_MANAGER" == "brew" ]]; then
            brew tap mongodb/brew
            brew install mongodb-community@7.0
        fi
        print_status "MongoDB installed successfully"
    fi
}

# Start MongoDB
start_mongodb() {
    echo "Starting MongoDB..."
    if [[ "$OS" == "linux" ]]; then
        sudo systemctl start mongod || sudo service mongod start
        sudo systemctl enable mongod || true
    elif [[ "$OS" == "macos" ]]; then
        brew services start mongodb-community@7.0
    fi
    sleep 3
    print_status "MongoDB started"
}

# Setup Python virtual environment and install dependencies
setup_python_env() {
    echo "Setting up Python environment..."
    cd "$APP_DIR/backend"
    
    # Create virtual environment if it doesn't exist
    if [ ! -d "venv" ]; then
        python3 -m venv venv
        print_status "Created Python virtual environment"
    fi
    
    # Activate virtual environment
    source venv/bin/activate
    
    # Upgrade pip
    pip install --upgrade pip
    
    # Install dependencies
    echo "Installing Python dependencies (this may take a few minutes)..."
    pip install -r requirements.txt
    
    # Install emergentintegrations from custom index
    pip install emergentintegrations --extra-index-url https://d33sy5i8bnduwe.cloudfront.net/simple/ || true
    
    print_status "Python dependencies installed"
}

# Setup environment files
setup_env_files() {
    echo "Setting up environment files..."
    
    # Backend .env
    if [ ! -f "$APP_DIR/backend/.env" ]; then
        cat > "$APP_DIR/backend/.env" << 'EOF'
# MongoDB Configuration
MONGO_URL=mongodb://localhost:27017
DB_NAME=atech_noc

# JWT Configuration
JWT_SECRET_KEY=atech-noc-commander-secret-key-change-in-production
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Server Configuration
HOST=0.0.0.0
PORT=8001
EOF
        print_status "Created backend/.env"
    else
        print_warning "backend/.env already exists, skipping"
    fi
    
    # Frontend .env
    if [ ! -f "$APP_DIR/frontend/.env" ]; then
        cat > "$APP_DIR/frontend/.env" << 'EOF'
REACT_APP_BACKEND_URL=http://localhost:8001
EOF
        print_status "Created frontend/.env"
    else
        print_warning "frontend/.env already exists, skipping"
    fi
}

# Build frontend if needed
build_frontend() {
    if [ ! -d "$APP_DIR/frontend/build" ]; then
        echo "Building frontend..."
        if command_exists node; then
            cd "$APP_DIR/frontend"
            npm install || yarn install
            npm run build || yarn build
            print_status "Frontend built successfully"
        else
            print_warning "Node.js not installed, skipping frontend build"
            print_warning "You can access the API at http://localhost:8001"
        fi
    else
        print_status "Frontend already built"
    fi
}

# Create startup scripts
create_startup_scripts() {
    echo "Creating startup scripts..."
    
    # Create start script
    cat > "$APP_DIR/start.sh" << 'EOF'
#!/bin/bash
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "Starting ATECH NOC Commander..."

# Start MongoDB if not running
if ! pgrep -x "mongod" > /dev/null; then
    echo "Starting MongoDB..."
    mongod --fork --logpath "$SCRIPT_DIR/mongodb/mongod.log" --dbpath "$SCRIPT_DIR/mongodb/data" 2>/dev/null || \
    sudo systemctl start mongod || \
    sudo service mongod start
fi

# Start backend
cd "$SCRIPT_DIR/backend"
source venv/bin/activate
nohup python -m uvicorn server:app --host 0.0.0.0 --port 8001 > ../logs/backend.log 2>&1 &
echo $! > ../pids/backend.pid
echo "Backend started on port 8001"

# Serve frontend
if [ -d "$SCRIPT_DIR/frontend/build" ]; then
    cd "$SCRIPT_DIR/frontend/build"
    nohup python3 -m http.server 3000 > ../../logs/frontend.log 2>&1 &
    echo $! > ../../pids/frontend.pid
    echo "Frontend started on port 3000"
fi

echo ""
echo "=========================================="
echo "  ATECH NOC Commander is running!"
echo "=========================================="
echo "  Web UI: http://localhost:3000"
echo "  API: http://localhost:8001"
echo ""
echo "  Default login:"
echo "    Email: admin@noc.com"
echo "    Password: admin123"
echo "=========================================="
EOF
    chmod +x "$APP_DIR/start.sh"
    
    # Create stop script
    cat > "$APP_DIR/stop.sh" << 'EOF'
#!/bin/bash
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "Stopping ATECH NOC Commander..."

# Stop backend
if [ -f "$SCRIPT_DIR/pids/backend.pid" ]; then
    kill $(cat "$SCRIPT_DIR/pids/backend.pid") 2>/dev/null
    rm "$SCRIPT_DIR/pids/backend.pid"
    echo "Backend stopped"
fi

# Stop frontend
if [ -f "$SCRIPT_DIR/pids/frontend.pid" ]; then
    kill $(cat "$SCRIPT_DIR/pids/frontend.pid") 2>/dev/null
    rm "$SCRIPT_DIR/pids/frontend.pid"
    echo "Frontend stopped"
fi

echo "ATECH NOC Commander stopped"
EOF
    chmod +x "$APP_DIR/stop.sh"
    
    print_status "Startup scripts created"
}

# Create necessary directories
create_directories() {
    mkdir -p "$APP_DIR/logs"
    mkdir -p "$APP_DIR/pids"
    mkdir -p "$APP_DIR/mongodb/data"
    print_status "Created necessary directories"
}

# Create systemd service (Linux only)
create_systemd_service() {
    if [[ "$OS" == "linux" ]]; then
        echo "Creating systemd service..."
        cat > /tmp/atech-noc.service << EOF
[Unit]
Description=ATECH NOC Commander
After=network.target mongod.service

[Service]
Type=forking
User=$USER
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/start.sh
ExecStop=$APP_DIR/stop.sh
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
        sudo mv /tmp/atech-noc.service /etc/systemd/system/
        sudo systemctl daemon-reload
        print_status "Systemd service created: atech-noc"
        echo "  To enable auto-start: sudo systemctl enable atech-noc"
    fi
}

# Create admin user in database
create_admin_user() {
    echo "Creating default admin user..."
    cd "$APP_DIR/backend"
    source venv/bin/activate
    python3 << 'PYTHON_EOF'
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from passlib.context import CryptContext
from datetime import datetime, timezone
import uuid
import os

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def create_admin():
    mongo_url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.getenv("DB_NAME", "atech_noc")
    
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    
    # Check if admin exists
    existing = await db.users.find_one({"email": "admin@noc.com"})
    if existing:
        print("Admin user already exists")
        return
    
    # Create admin user
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
    print("Admin user created: admin@noc.com / admin123")
    
    client.close()

asyncio.run(create_admin())
PYTHON_EOF
    print_status "Admin user created"
}

# Main installation
main() {
    detect_os
    echo ""
    
    echo "Step 1/8: Installing Python..."
    install_python
    echo ""
    
    echo "Step 2/8: Installing MongoDB..."
    install_mongodb
    echo ""
    
    echo "Step 3/8: Starting MongoDB..."
    start_mongodb
    echo ""
    
    echo "Step 4/8: Creating directories..."
    create_directories
    echo ""
    
    echo "Step 5/8: Setting up Python environment..."
    setup_python_env
    echo ""
    
    echo "Step 6/8: Setting up environment files..."
    setup_env_files
    echo ""
    
    echo "Step 7/8: Creating startup scripts..."
    create_startup_scripts
    echo ""
    
    echo "Step 8/8: Creating admin user..."
    create_admin_user
    echo ""
    
    # Create systemd service on Linux
    create_systemd_service
    
    echo ""
    echo -e "${GREEN}=========================================="
    echo "  INSTALLATION COMPLETE!"
    echo "==========================================${NC}"
    echo ""
    echo "To start the application:"
    echo "  ./start.sh"
    echo ""
    echo "To stop the application:"
    echo "  ./stop.sh"
    echo ""
    echo "Access the application at:"
    echo "  http://localhost:3000"
    echo ""
    echo "Default credentials:"
    echo "  Email: admin@noc.com"
    echo "  Password: admin123"
    echo ""
}

main "$@"
