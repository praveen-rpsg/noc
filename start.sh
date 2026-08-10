#!/bin/bash
# ATECH NOC Commander - Start Script for Linux/macOS

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "=========================================="
echo "  Starting ATECH NOC Commander..."
echo "=========================================="

# Create directories if they don't exist
mkdir -p "$SCRIPT_DIR/logs"
mkdir -p "$SCRIPT_DIR/pids"

# Check if MongoDB is running
if ! pgrep -x "mongod" > /dev/null; then
    echo "Starting MongoDB..."
    if [ -d "$SCRIPT_DIR/mongodb/data" ]; then
        mongod --fork --logpath "$SCRIPT_DIR/logs/mongod.log" --dbpath "$SCRIPT_DIR/mongodb/data" 2>/dev/null
    else
        # Try system MongoDB
        sudo systemctl start mongod 2>/dev/null || sudo service mongod start 2>/dev/null
    fi
    sleep 2
fi

# Check MongoDB connection
if ! mongo --eval "db.adminCommand('ping')" --quiet 2>/dev/null && \
   ! mongosh --eval "db.adminCommand('ping')" --quiet 2>/dev/null; then
    echo "[WARNING] MongoDB may not be running. Backend will retry connection."
fi

# Start backend
echo "Starting backend server..."
cd "$SCRIPT_DIR/backend"

if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Kill existing backend if running
if [ -f "$SCRIPT_DIR/pids/backend.pid" ]; then
    kill $(cat "$SCRIPT_DIR/pids/backend.pid") 2>/dev/null
    rm "$SCRIPT_DIR/pids/backend.pid"
fi

nohup python -m uvicorn server:app --host 0.0.0.0 --port 8001 > "$SCRIPT_DIR/logs/backend.log" 2>&1 &
echo $! > "$SCRIPT_DIR/pids/backend.pid"
echo "[OK] Backend started on port 8001 (PID: $(cat $SCRIPT_DIR/pids/backend.pid))"

# Start frontend
if [ -d "$SCRIPT_DIR/frontend/build" ]; then
    echo "Starting frontend server..."
    cd "$SCRIPT_DIR/frontend/build"
    
    # Kill existing frontend if running
    if [ -f "$SCRIPT_DIR/pids/frontend.pid" ]; then
        kill $(cat "$SCRIPT_DIR/pids/frontend.pid") 2>/dev/null
        rm "$SCRIPT_DIR/pids/frontend.pid"
    fi
    
    nohup python3 -m http.server 3000 > "$SCRIPT_DIR/logs/frontend.log" 2>&1 &
    echo $! > "$SCRIPT_DIR/pids/frontend.pid"
    echo "[OK] Frontend started on port 3000 (PID: $(cat $SCRIPT_DIR/pids/frontend.pid))"
else
    echo "[!] Frontend build not found. API available at http://localhost:8001"
fi

# Wait for services to start
sleep 3

echo ""
echo "=========================================="
echo "  ATECH NOC Commander is running!"
echo "=========================================="
echo ""
echo "  Web Application: http://localhost:3000"
echo "  API Endpoint:    http://localhost:8001"
echo "  API Docs:        http://localhost:8001/docs"
echo ""
echo "  Default credentials:"
echo "    Email:    admin@noc.com"
echo "    Password: admin123"
echo ""
echo "  Logs: $SCRIPT_DIR/logs/"
echo "=========================================="
echo ""
echo "To stop: ./stop.sh"
