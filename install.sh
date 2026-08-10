#!/bin/bash

# ATECH NOC Commander - Quick Start Script
# This script helps set up the application on a standalone system

set -e

echo "============================================"
echo "  ATECH NOC Commander - Installation Script"
echo "============================================"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo -e "${YELLOW}Warning: Running as root. Consider using a non-root user.${NC}"
fi

# Detect OS
detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$ID
        VERSION=$VERSION_ID
    elif [ -f /etc/debian_version ]; then
        OS="debian"
    elif [ -f /etc/redhat-release ]; then
        OS="rhel"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        OS="macos"
    else
        OS="unknown"
    fi
    echo "Detected OS: $OS"
}

# Check dependencies
check_dependencies() {
    echo ""
    echo "Checking dependencies..."
    
    # Python
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
        echo -e "${GREEN}✓${NC} Python: $PYTHON_VERSION"
    else
        echo -e "${RED}✗${NC} Python 3 not found"
        MISSING_DEPS+=("python3")
    fi
    
    # Node.js
    if command -v node &> /dev/null; then
        NODE_VERSION=$(node --version)
        echo -e "${GREEN}✓${NC} Node.js: $NODE_VERSION"
    else
        echo -e "${RED}✗${NC} Node.js not found"
        MISSING_DEPS+=("nodejs")
    fi
    
    # Yarn
    if command -v yarn &> /dev/null; then
        YARN_VERSION=$(yarn --version)
        echo -e "${GREEN}✓${NC} Yarn: $YARN_VERSION"
    else
        echo -e "${RED}✗${NC} Yarn not found"
        MISSING_DEPS+=("yarn")
    fi
    
    # MongoDB
    if command -v mongod &> /dev/null; then
        MONGO_VERSION=$(mongod --version | head -1)
        echo -e "${GREEN}✓${NC} MongoDB: installed"
    else
        echo -e "${RED}✗${NC} MongoDB not found"
        MISSING_DEPS+=("mongodb")
    fi
    
    # Git
    if command -v git &> /dev/null; then
        GIT_VERSION=$(git --version)
        echo -e "${GREEN}✓${NC} Git: $GIT_VERSION"
    else
        echo -e "${RED}✗${NC} Git not found"
        MISSING_DEPS+=("git")
    fi
}

# Install missing dependencies (Ubuntu/Debian)
install_dependencies_debian() {
    echo ""
    echo "Installing missing dependencies..."
    
    sudo apt update
    
    for dep in "${MISSING_DEPS[@]}"; do
        case $dep in
            python3)
                sudo apt install -y python3 python3-pip python3-venv
                ;;
            nodejs)
                curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
                sudo apt install -y nodejs
                ;;
            yarn)
                sudo npm install -g yarn
                ;;
            mongodb)
                wget -qO - https://www.mongodb.org/static/pgp/server-6.0.asc | sudo apt-key add -
                echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu $(lsb_release -cs)/mongodb-org/6.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-6.0.list
                sudo apt update
                sudo apt install -y mongodb-org
                sudo systemctl enable mongod
                sudo systemctl start mongod
                ;;
            git)
                sudo apt install -y git
                ;;
        esac
    done
}

# Setup Backend
setup_backend() {
    echo ""
    echo "Setting up Backend..."
    
    cd backend
    
    # Create virtual environment
    python3 -m venv venv
    source venv/bin/activate
    
    # Install dependencies
    pip install --upgrade pip
    pip install -r requirements.txt
    
    # Create .env if not exists
    if [ ! -f .env ]; then
        echo "Creating backend .env file..."
        cat > .env << EOF
MONGO_URL=mongodb://localhost:27017
DB_NAME=noc_commander
JWT_SECRET=$(openssl rand -hex 32)
EOF
        echo -e "${GREEN}✓${NC} Backend .env created"
    else
        echo -e "${YELLOW}!${NC} Backend .env already exists, skipping"
    fi
    
    cd ..
    echo -e "${GREEN}✓${NC} Backend setup complete"
}

# Setup Frontend
setup_frontend() {
    echo ""
    echo "Setting up Frontend..."
    
    cd frontend
    
    # Install dependencies
    yarn install
    
    # Create .env if not exists
    if [ ! -f .env ]; then
        echo "Creating frontend .env file..."
        cat > .env << EOF
REACT_APP_BACKEND_URL=http://localhost:8001
EOF
        echo -e "${GREEN}✓${NC} Frontend .env created"
    else
        echo -e "${YELLOW}!${NC} Frontend .env already exists, skipping"
    fi
    
    cd ..
    echo -e "${GREEN}✓${NC} Frontend setup complete"
}

# Start services
start_services() {
    echo ""
    echo "Starting services..."
    
    # Check MongoDB
    if ! systemctl is-active --quiet mongod 2>/dev/null; then
        echo "Starting MongoDB..."
        sudo systemctl start mongod || mongod --fork --logpath /var/log/mongod.log
    fi
    echo -e "${GREEN}✓${NC} MongoDB running"
    
    # Start Backend
    echo "Starting Backend on port 8001..."
    cd backend
    source venv/bin/activate
    nohup uvicorn server:app --host 0.0.0.0 --port 8001 > ../backend.log 2>&1 &
    BACKEND_PID=$!
    echo $BACKEND_PID > ../backend.pid
    cd ..
    sleep 3
    
    # Check backend health
    if curl -s http://localhost:8001/api/health > /dev/null; then
        echo -e "${GREEN}✓${NC} Backend running (PID: $BACKEND_PID)"
    else
        echo -e "${RED}✗${NC} Backend failed to start. Check backend.log"
        return 1
    fi
    
    # Start Frontend
    echo "Starting Frontend on port 3000..."
    cd frontend
    nohup yarn start > ../frontend.log 2>&1 &
    FRONTEND_PID=$!
    echo $FRONTEND_PID > ../frontend.pid
    cd ..
    sleep 5
    echo -e "${GREEN}✓${NC} Frontend running (PID: $FRONTEND_PID)"
}

# Print summary
print_summary() {
    echo ""
    echo "============================================"
    echo "  Installation Complete!"
    echo "============================================"
    echo ""
    echo "Access the application:"
    echo "  - Frontend: http://localhost:3000"
    echo "  - Backend API: http://localhost:8001"
    echo "  - Health Check: http://localhost:8001/api/health"
    echo ""
    echo "Default credentials:"
    echo "  - Email: admin@noc.com"
    echo "  - Password: admin123"
    echo ""
    echo "To stop services:"
    echo "  kill \$(cat backend.pid) \$(cat frontend.pid)"
    echo ""
    echo "Logs:"
    echo "  - Backend: backend.log"
    echo "  - Frontend: frontend.log"
    echo ""
}

# Main
main() {
    MISSING_DEPS=()
    
    detect_os
    check_dependencies
    
    if [ ${#MISSING_DEPS[@]} -gt 0 ]; then
        echo ""
        echo -e "${YELLOW}Missing dependencies: ${MISSING_DEPS[*]}${NC}"
        read -p "Install missing dependencies? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            case $OS in
                ubuntu|debian)
                    install_dependencies_debian
                    ;;
                *)
                    echo "Automatic installation not supported for $OS"
                    echo "Please install manually: ${MISSING_DEPS[*]}"
                    exit 1
                    ;;
            esac
        else
            echo "Please install missing dependencies and run again."
            exit 1
        fi
    fi
    
    setup_backend
    setup_frontend
    
    read -p "Start services now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        start_services
    fi
    
    print_summary
}

# Run main
main "$@"
