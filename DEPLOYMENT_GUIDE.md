# ATECH NOC Commander - System Requirements & Deployment Guide

## Table of Contents
1. [Application Overview](#application-overview)
2. [Standalone/On-Premise Deployment](#standaloneon-premise-deployment)
3. [Cloud Deployment](#cloud-deployment)
4. [Database Requirements](#database-requirements)
5. [Network Requirements](#network-requirements)
6. [Security Considerations](#security-considerations)
7. [Installation Steps](#installation-steps)

---

## Application Overview

**ATECH NOC Commander** is an AI-powered Network Operation Center tool consisting of:
- **Frontend**: React 19 web application (or Electron desktop app)
- **Backend**: Python FastAPI REST API server
- **Database**: MongoDB (document database)
- **AI Integration**: OpenAI GPT for intelligent incident analysis

---

## Standalone/On-Premise Deployment

### Minimum Hardware Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU | 2 cores | 4+ cores |
| RAM | 4 GB | 8+ GB |
| Storage | 20 GB SSD | 50+ GB SSD |
| Network | 100 Mbps | 1 Gbps |

### Software Requirements

#### Operating System
- **Windows**: Windows 10/11, Windows Server 2019/2022
- **Linux**: Ubuntu 20.04+, CentOS 8+, RHEL 8+, Debian 11+
- **macOS**: macOS 11 (Big Sur) or later

#### Runtime Dependencies

| Software | Version | Purpose |
|----------|---------|---------|
| Python | 3.10+ | Backend runtime |
| Node.js | 18.x+ | Frontend build/development |
| MongoDB | 6.0+ | Database |
| Yarn | 1.22+ | Package manager |
| Git | 2.30+ | Version control |

#### Python Packages (Backend)
```
fastapi>=0.109.0
uvicorn>=0.27.0
motor>=3.3.0              # Async MongoDB driver
pydantic>=2.5.0
python-jose>=3.3.0        # JWT tokens
passlib>=1.7.4            # Password hashing
bcrypt>=4.1.0
python-multipart>=0.0.6
websockets>=12.0
httpx>=0.26.0
reportlab>=4.0.0          # PDF generation
litellm>=1.0.0            # LLM integration
emergentintegrations      # Emergent AI key support
```

#### Node.js Packages (Frontend)
- React 19.x
- Axios (HTTP client)
- TailwindCSS (styling)
- Radix UI (components)
- Recharts (charts)
- Lucide React (icons)

#### For Desktop App (Electron)
| Software | Version | Purpose |
|----------|---------|---------|
| Electron | 28.x | Desktop wrapper |
| electron-builder | 24.x | Packaging |

---

## Cloud Deployment

### Option 1: Virtual Machine (IaaS)

#### AWS EC2 / Azure VM / GCP Compute Engine

| Tier | Instance Type | vCPUs | RAM | Storage | Use Case |
|------|--------------|-------|-----|---------|----------|
| Small | t3.medium / B2s / e2-medium | 2 | 4 GB | 30 GB | Dev/Test |
| Medium | t3.large / B2ms / e2-standard-2 | 2 | 8 GB | 50 GB | Small NOC |
| Large | t3.xlarge / B4ms / e2-standard-4 | 4 | 16 GB | 100 GB | Production |
| Enterprise | m5.2xlarge / D4s_v3 / n2-standard-8 | 8 | 32 GB | 200 GB | Large NOC |

#### Required Cloud Services
- **Compute**: VM instance
- **Storage**: Block storage (SSD recommended)
- **Database**: MongoDB Atlas OR self-hosted MongoDB
- **Networking**: VPC, Security Groups, Load Balancer (optional)
- **DNS**: Route 53 / Azure DNS / Cloud DNS

### Option 2: Container-Based (PaaS)

#### Docker Requirements
```yaml
# docker-compose.yml structure
services:
  backend:
    image: python:3.11-slim
    ports: ["8001:8001"]
    environment:
      - MONGO_URL=mongodb://mongodb:27017
      - DB_NAME=noc_commander
    
  frontend:
    image: node:18-alpine
    ports: ["3000:3000"]
    
  mongodb:
    image: mongo:6.0
    volumes: ["mongo_data:/data/db"]
```

#### Kubernetes (EKS/AKS/GKE)
| Component | Resources |
|-----------|-----------|
| Backend Pod | 500m-1000m CPU, 512Mi-1Gi RAM |
| Frontend Pod | 250m-500m CPU, 256Mi-512Mi RAM |
| MongoDB Pod | 1000m-2000m CPU, 2Gi-4Gi RAM |

### Option 3: Serverless / Managed Services

| Component | AWS | Azure | GCP |
|-----------|-----|-------|-----|
| Backend | ECS Fargate / Lambda | Container Apps | Cloud Run |
| Frontend | S3 + CloudFront | Blob + CDN | Cloud Storage + CDN |
| Database | DocumentDB / MongoDB Atlas | Cosmos DB | MongoDB Atlas |
| Secrets | Secrets Manager | Key Vault | Secret Manager |

---

## Database Requirements

### MongoDB Specifications

| Deployment | Version | Storage | Connections |
|------------|---------|---------|-------------|
| Development | 6.0+ | 5 GB | 10 |
| Production | 6.0+ | 50+ GB | 100+ |
| Enterprise | 7.0+ | 200+ GB | 500+ |

### Collections Used
```
users              # User accounts
devices            # Network devices
incidents          # Incident tickets
alerts             # System alerts
performance        # Performance metrics
assets             # Asset inventory
reports            # Generated reports
sla_definitions    # SLA configurations
config_backups     # Configuration snapshots
escalation_levels  # Escalation rules
agent_executions   # AI agent logs
pending_actions    # Actions awaiting approval
settings_*         # Various configuration stores
```

### MongoDB Atlas Tiers (Cloud)
| Tier | RAM | Storage | Price (approx) |
|------|-----|---------|----------------|
| M0 (Free) | Shared | 512 MB | Free |
| M10 | 2 GB | 10 GB | ~$60/month |
| M20 | 4 GB | 20 GB | ~$140/month |
| M30 | 8 GB | 40 GB | ~$280/month |

---

## Network Requirements

### Ports

| Port | Protocol | Service | Direction |
|------|----------|---------|-----------|
| 3000 | TCP | Frontend (dev) | Inbound |
| 8001 | TCP | Backend API | Inbound |
| 27017 | TCP | MongoDB | Internal |
| 443 | TCP | HTTPS | Inbound |
| 80 | TCP | HTTP (redirect) | Inbound |

### Firewall Rules
```
# Allow frontend access
ALLOW TCP 443 FROM 0.0.0.0/0

# Allow API access (if exposed)
ALLOW TCP 8001 FROM <frontend_ip>/32

# MongoDB (internal only)
ALLOW TCP 27017 FROM <backend_ip>/32

# Outbound for AI API
ALLOW TCP 443 TO api.openai.com
ALLOW TCP 443 TO api.anthropic.com
```

### Bandwidth Requirements
| Users | Minimum | Recommended |
|-------|---------|-------------|
| 1-10 | 10 Mbps | 50 Mbps |
| 10-50 | 50 Mbps | 100 Mbps |
| 50-200 | 100 Mbps | 500 Mbps |
| 200+ | 500 Mbps | 1 Gbps |

---

## Security Considerations

### Authentication & Authorization
- JWT-based authentication with configurable expiration
- Role-based access control (Admin, Operator)
- Password hashing with bcrypt

### Encryption
- **In Transit**: TLS 1.2+ for all connections
- **At Rest**: MongoDB encryption (Enterprise) or disk encryption

### Environment Variables (Sensitive)
```bash
# Backend (.env)
MONGO_URL=mongodb://...        # Database connection
JWT_SECRET=<random-256-bit>    # Token signing key
OPENAI_API_KEY=sk-...          # AI integration
EMERGENT_API_KEY=...           # Emergent LLM key (optional)

# Frontend (.env)
REACT_APP_BACKEND_URL=https://api.yournoc.com
```

### Recommended Security Measures
1. **SSL/TLS Certificate** - Use Let's Encrypt or commercial cert
2. **Reverse Proxy** - Nginx/Traefik in front of services
3. **Rate Limiting** - Prevent API abuse
4. **CORS Configuration** - Restrict allowed origins
5. **Database Authentication** - Enable MongoDB auth
6. **Regular Backups** - Automated MongoDB backups
7. **Audit Logging** - Track user actions

---

## Installation Steps

### Standalone Deployment (Linux)

```bash
# 1. Install system dependencies
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3-pip nodejs npm git

# 2. Install MongoDB
wget -qO - https://www.mongodb.org/static/pgp/server-6.0.asc | sudo apt-key add -
echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu focal/mongodb-org/6.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-6.0.list
sudo apt update
sudo apt install -y mongodb-org
sudo systemctl enable mongod
sudo systemctl start mongod

# 3. Install Yarn
npm install -g yarn

# 4. Clone repository
git clone https://github.com/your-repo/atech-noc-commander.git
cd atech-noc-commander

# 5. Setup Backend
cd backend
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create .env file
cat > .env << EOF
MONGO_URL=mongodb://localhost:27017
DB_NAME=noc_commander
JWT_SECRET=$(openssl rand -hex 32)
EOF

# 6. Setup Frontend
cd ../frontend
yarn install

# Create .env file
cat > .env << EOF
REACT_APP_BACKEND_URL=http://localhost:8001
EOF

# 7. Build Frontend for Production
yarn build

# 8. Start Services (Production)
# Backend (use gunicorn or uvicorn)
cd ../backend
source venv/bin/activate
uvicorn server:app --host 0.0.0.0 --port 8001 &

# Frontend (serve static build with nginx)
sudo cp -r ../frontend/build /var/www/noc-commander
```

### Docker Deployment

```bash
# 1. Create docker-compose.yml
cat > docker-compose.yml << 'EOF'
version: '3.8'
services:
  mongodb:
    image: mongo:6.0
    volumes:
      - mongo_data:/data/db
    restart: always

  backend:
    build: ./backend
    ports:
      - "8001:8001"
    environment:
      - MONGO_URL=mongodb://mongodb:27017
      - DB_NAME=noc_commander
      - JWT_SECRET=${JWT_SECRET}
    depends_on:
      - mongodb
    restart: always

  frontend:
    build: ./frontend
    ports:
      - "3000:80"
    depends_on:
      - backend
    restart: always

volumes:
  mongo_data:
EOF

# 2. Create Backend Dockerfile
cat > backend/Dockerfile << 'EOF'
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8001"]
EOF

# 3. Create Frontend Dockerfile
cat > frontend/Dockerfile << 'EOF'
FROM node:18-alpine AS build
WORKDIR /app
COPY package.json yarn.lock ./
RUN yarn install
COPY . .
RUN yarn build

FROM nginx:alpine
COPY --from=build /app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
EOF

# 4. Start containers
docker-compose up -d
```

### Desktop App Build (Electron)

```bash
cd frontend

# Windows
yarn electron:build:win
# Output: frontend/dist/ATECH NOC Commander-1.0.0-win-x64.exe

# macOS
yarn electron:build:mac
# Output: frontend/dist/ATECH NOC Commander-1.0.0-mac-x64.dmg

# Linux
yarn electron:build:linux
# Output: frontend/dist/ATECH-NOC-Commander-1.0.0-linux.AppImage
```

---

## Post-Installation Checklist

- [ ] MongoDB is running and accessible
- [ ] Backend API responds at `/api/health`
- [ ] Frontend loads without errors
- [ ] Login works with test credentials
- [ ] SSL/TLS configured (production)
- [ ] Firewall rules configured
- [ ] Backup schedule configured
- [ ] Monitoring/alerting configured
- [ ] AI API key configured (for intelligent features)

---

## Support & Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| Cannot connect to MongoDB | Check MongoDB service status, verify MONGO_URL |
| Login fails | Verify backend is running, check JWT_SECRET |
| AI features not working | Verify OPENAI_API_KEY or EMERGENT_API_KEY |
| CORS errors | Check REACT_APP_BACKEND_URL matches actual backend |
| Desktop app can't connect | Configure Server Settings on login page |

### Log Locations
- Backend: stdout/stderr or configured log file
- Frontend: Browser console (F12)
- MongoDB: `/var/log/mongodb/mongod.log`
- Docker: `docker-compose logs -f`

---

## Contact

For enterprise support or custom deployment assistance, contact:
- **Company**: Ameya Technology
- **Product**: ATECH NOC Commander

---

*Document Version: 1.0*
*Last Updated: April 2026*
