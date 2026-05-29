#!/bin/bash
# ATECH NOC Commander - Docker Helper Script

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

print_header() {
    echo -e "${BLUE}"
    echo "=========================================="
    echo "  ATECH NOC COMMANDER - Docker Manager"
    echo "=========================================="
    echo -e "${NC}"
}

print_status() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

# Check if .env exists
check_env() {
    if [ ! -f ".env" ]; then
        print_warning ".env file not found. Creating from template..."
        cp docker/.env.example .env
        print_status "Created .env file. Please edit it with your configuration."
        echo ""
        echo "Required settings:"
        echo "  - MONGO_ROOT_PASSWORD"
        echo "  - JWT_SECRET_KEY"
        echo ""
        echo "Run: nano .env"
        exit 1
    fi
}

# Start services
start() {
    print_header
    check_env
    
    local mode=${1:-dev}
    
    if [ "$mode" == "prod" ]; then
        echo "Starting in PRODUCTION mode..."
        docker-compose -f docker-compose.prod.yml up -d --build
    else
        echo "Starting in DEVELOPMENT mode..."
        docker-compose up -d --build
    fi
    
    echo ""
    print_status "Services starting..."
    echo ""
    echo "Waiting for services to be healthy..."
    sleep 10
    
    docker-compose ps
    
    echo ""
    echo -e "${GREEN}=========================================="
    echo "  ATECH NOC Commander is running!"
    echo "==========================================${NC}"
    echo ""
    echo "  Web UI:   http://localhost:3000"
    echo "  API:      http://localhost:8001"
    echo "  API Docs: http://localhost:8001/docs"
    echo ""
    echo "  Default login:"
    echo "    Email:    admin@noc.com"
    echo "    Password: admin123"
    echo ""
}

# Stop services
stop() {
    print_header
    echo "Stopping services..."
    docker-compose down
    print_status "Services stopped"
}

# Restart services
restart() {
    print_header
    echo "Restarting services..."
    docker-compose restart
    print_status "Services restarted"
}

# View logs
logs() {
    local service=$1
    if [ -n "$service" ]; then
        docker-compose logs -f "$service"
    else
        docker-compose logs -f
    fi
}

# Show status
status() {
    print_header
    docker-compose ps
    echo ""
    echo "Health Status:"
    for container in $(docker-compose ps -q); do
        name=$(docker inspect --format='{{.Name}}' "$container" | sed 's/\///')
        health=$(docker inspect --format='{{.State.Health.Status}}' "$container" 2>/dev/null || echo "N/A")
        echo "  $name: $health"
    done
}

# Rebuild services
rebuild() {
    print_header
    echo "Rebuilding services..."
    docker-compose build --no-cache
    print_status "Rebuild complete"
    echo ""
    echo "Run './docker.sh start' to start the new containers"
}

# Backup database
backup() {
    print_header
    local backup_dir="backups/$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$backup_dir"
    
    echo "Creating database backup..."
    
    # Get MongoDB credentials from .env
    source .env
    
    docker-compose exec -T mongodb mongodump \
        --username "${MONGO_ROOT_USERNAME:-admin}" \
        --password "${MONGO_ROOT_PASSWORD}" \
        --authenticationDatabase admin \
        --archive > "$backup_dir/mongodb_backup.archive"
    
    print_status "Backup saved to: $backup_dir/mongodb_backup.archive"
}

# Restore database
restore() {
    print_header
    local backup_file=$1
    
    if [ -z "$backup_file" ]; then
        print_error "Please specify backup file"
        echo "Usage: ./docker.sh restore <backup_file>"
        exit 1
    fi
    
    if [ ! -f "$backup_file" ]; then
        print_error "Backup file not found: $backup_file"
        exit 1
    fi
    
    echo "Restoring database from: $backup_file"
    
    # Get MongoDB credentials from .env
    source .env
    
    docker-compose exec -T mongodb mongorestore \
        --username "${MONGO_ROOT_USERNAME:-admin}" \
        --password "${MONGO_ROOT_PASSWORD}" \
        --authenticationDatabase admin \
        --archive < "$backup_file"
    
    print_status "Database restored"
}

# Clean up
clean() {
    print_header
    print_warning "This will remove all containers, volumes, and images!"
    read -p "Are you sure? (y/N): " confirm
    
    if [ "$confirm" == "y" ] || [ "$confirm" == "Y" ]; then
        docker-compose down -v --rmi local
        print_status "Cleanup complete"
    else
        echo "Cancelled"
    fi
}

# Show help
help() {
    print_header
    echo "Usage: ./docker.sh <command> [options]"
    echo ""
    echo "Commands:"
    echo "  start [dev|prod]  Start services (default: dev)"
    echo "  stop              Stop all services"
    echo "  restart           Restart all services"
    echo "  status            Show service status"
    echo "  logs [service]    View logs (all or specific service)"
    echo "  rebuild           Rebuild all images"
    echo "  backup            Backup MongoDB database"
    echo "  restore <file>    Restore MongoDB from backup"
    echo "  clean             Remove all containers and volumes"
    echo "  help              Show this help message"
    echo ""
    echo "Examples:"
    echo "  ./docker.sh start           # Start in development mode"
    echo "  ./docker.sh start prod      # Start in production mode"
    echo "  ./docker.sh logs backend    # View backend logs"
    echo "  ./docker.sh backup          # Create database backup"
    echo ""
}

# Main
case "${1:-help}" in
    start)
        start "$2"
        ;;
    stop)
        stop
        ;;
    restart)
        restart
        ;;
    status)
        status
        ;;
    logs)
        logs "$2"
        ;;
    rebuild)
        rebuild
        ;;
    backup)
        backup
        ;;
    restore)
        restore "$2"
        ;;
    clean)
        clean
        ;;
    help|--help|-h)
        help
        ;;
    *)
        print_error "Unknown command: $1"
        help
        exit 1
        ;;
esac
