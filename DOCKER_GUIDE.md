# ATECH NOC Commander - Docker Deployment Guide

## Quick Start

### Prerequisites
- Docker Engine 20.10+
- Docker Compose 2.0+
- 4GB RAM minimum
- 10GB disk space

### 1. Clone and Configure

```bash
# Navigate to project directory
cd atech-noc-commander

# Copy environment file
cp docker/.env.example .env

# Edit configuration
nano .env
```

### 2. Start Services

```bash
# Development mode
docker-compose up -d

# Production mode (with SSL)
docker-compose -f docker-compose.prod.yml up -d
```

### 3. Access Application

| Service | URL |
|---------|-----|
| Web UI | http://localhost:3000 |
| API | http://localhost:8001 |
| API Docs | http://localhost:8001/docs |

**Default Credentials:**
- Email: `admin@noc.com`
- Password: `admin123`

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Docker Network                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────┐    ┌──────────┐    ┌──────────────────────┐  │
│  │  Nginx   │───▶│ Frontend │    │       MongoDB        │  │
│  │  :80/:443│    │  :3000   │    │       :27017         │  │
│  └────┬─────┘    └──────────┘    └──────────────────────┘  │
│       │                                    ▲                │
│       │          ┌──────────┐              │                │
│       └─────────▶│ Backend  │──────────────┘                │
│                  │  :8001   │                               │
│                  └──────────┘                               │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Docker Commands

### Basic Operations

```bash
# Start all services
docker-compose up -d

# Stop all services
docker-compose down

# View logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose logs -f mongodb

# Restart a service
docker-compose restart backend

# Rebuild images
docker-compose build --no-cache

# Remove all containers and volumes
docker-compose down -v
```

### Scaling (Production)

```bash
# Scale backend instances
docker-compose -f docker-compose.prod.yml up -d --scale backend=3
```

---

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MONGO_ROOT_USERNAME` | MongoDB admin username | `admin` |
| `MONGO_ROOT_PASSWORD` | MongoDB admin password | Required |
| `DB_NAME` | Database name | `atech_noc` |
| `JWT_SECRET_KEY` | JWT signing key | Required |
| `EMERGENT_LLM_KEY` | AI features key | Optional |
| `REACT_APP_BACKEND_URL` | External API URL | Auto |

### Generate Secure Keys

```bash
# Generate JWT secret
openssl rand -hex 32

# Generate MongoDB password
openssl rand -base64 24
```

---

## Production Deployment

### 1. SSL Certificates

```bash
# Create SSL directory
mkdir -p docker/ssl

# Option A: Let's Encrypt (recommended)
certbot certonly --standalone -d your-domain.com
cp /etc/letsencrypt/live/your-domain.com/fullchain.pem docker/ssl/
cp /etc/letsencrypt/live/your-domain.com/privkey.pem docker/ssl/

# Option B: Self-signed (development only)
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout docker/ssl/privkey.pem \
  -out docker/ssl/fullchain.pem
```

### 2. Configure Production Environment

```bash
# Copy and edit production env
cp docker/.env.example .env

# Set secure values
nano .env
```

**Required for Production:**
```env
MONGO_ROOT_PASSWORD=<strong-password>
JWT_SECRET_KEY=<generated-key>
```

### 3. Deploy

```bash
# Build and start
docker-compose -f docker-compose.prod.yml up -d --build

# Verify all services are healthy
docker-compose -f docker-compose.prod.yml ps
```

---

## Backup & Restore

### Backup MongoDB

```bash
# Create backup
docker-compose exec mongodb mongodump \
  --username admin \
  --password <password> \
  --authenticationDatabase admin \
  --out /dump

# Copy backup to host
docker cp atech-noc-mongodb:/dump ./backup_$(date +%Y%m%d)
```

### Restore MongoDB

```bash
# Copy backup to container
docker cp ./backup_20240101 atech-noc-mongodb:/dump

# Restore
docker-compose exec mongodb mongorestore \
  --username admin \
  --password <password> \
  --authenticationDatabase admin \
  /dump
```

---

## Troubleshooting

### Common Issues

**1. MongoDB Connection Failed**
```bash
# Check MongoDB logs
docker-compose logs mongodb

# Verify MongoDB is healthy
docker-compose exec mongodb mongosh --eval "db.adminCommand('ping')"
```

**2. Backend Not Starting**
```bash
# Check backend logs
docker-compose logs backend

# Verify environment variables
docker-compose exec backend env | grep MONGO
```

**3. Frontend Not Loading**
```bash
# Check nginx configuration
docker-compose exec frontend nginx -t

# Rebuild frontend
docker-compose build --no-cache frontend
docker-compose up -d frontend
```

**4. Port Already in Use**
```bash
# Find process using port
lsof -i :3000
lsof -i :8001

# Kill process
kill -9 <PID>
```

### Health Checks

```bash
# Check all service health
docker-compose ps

# Check specific service
docker inspect --format='{{.State.Health.Status}}' atech-noc-backend
```

---

## Resource Requirements

### Minimum
| Service | CPU | Memory |
|---------|-----|--------|
| MongoDB | 0.5 | 512MB |
| Backend | 0.5 | 512MB |
| Frontend | 0.25 | 128MB |

### Recommended (Production)
| Service | CPU | Memory |
|---------|-----|--------|
| MongoDB | 2 | 2GB |
| Backend | 2 | 2GB |
| Frontend | 1 | 512MB |
| Nginx | 0.5 | 256MB |

---

## Updating

```bash
# Pull latest changes
git pull origin main

# Rebuild and restart
docker-compose down
docker-compose build --no-cache
docker-compose up -d

# Verify
docker-compose ps
docker-compose logs -f
```

---

*Last Updated: May 2026*
