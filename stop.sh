#!/bin/bash
# ATECH NOC Commander - Stop Script for Linux/macOS

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "=========================================="
echo "  Stopping ATECH NOC Commander..."
echo "=========================================="

# Stop backend
if [ -f "$SCRIPT_DIR/pids/backend.pid" ]; then
    PID=$(cat "$SCRIPT_DIR/pids/backend.pid")
    if kill -0 $PID 2>/dev/null; then
        kill $PID
        echo "[OK] Backend stopped (PID: $PID)"
    fi
    rm "$SCRIPT_DIR/pids/backend.pid"
else
    # Try to find and kill uvicorn process
    pkill -f "uvicorn server:app" 2>/dev/null && echo "[OK] Backend process killed"
fi

# Stop frontend
if [ -f "$SCRIPT_DIR/pids/frontend.pid" ]; then
    PID=$(cat "$SCRIPT_DIR/pids/frontend.pid")
    if kill -0 $PID 2>/dev/null; then
        kill $PID
        echo "[OK] Frontend stopped (PID: $PID)"
    fi
    rm "$SCRIPT_DIR/pids/frontend.pid"
else
    # Try to find and kill http.server on port 3000
    lsof -ti:3000 | xargs kill 2>/dev/null && echo "[OK] Frontend process killed"
fi

echo ""
echo "ATECH NOC Commander stopped."
echo ""
echo "Note: MongoDB service is still running."
echo "To stop MongoDB: sudo systemctl stop mongod"
