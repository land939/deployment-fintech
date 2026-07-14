# Docker Deployment Guide - GTA Fintech Platform

Complete guide to containerizing and deploying the GTA Fintech application using Docker and Docker Compose.

## 📋 Table of Contents

1. [Quick Start](#quick-start)
2. [Architecture](#architecture)
3. [Installation](#installation)
4. [Configuration](#configuration)
5. [Running Containers](#running-containers)
6. [Common Operations](#common-operations)
7. [Troubleshooting](#troubleshooting)
8. [Production Deployment](#production-deployment)

## 🚀 Quick Start

### Minimum 5-Minute Setup

```bash
# 1. Navigate to project root
cd /path/to/code_memoire

# 2. Copy environment template
cp docker/.env.docker .env

# 3. Update critical secrets in .env
nano .env
# Change: SECRET_KEY, DB_PASSWORD, SUPERADMIN_EMAIL

# 4. Build and start containers
make docker-up

# 5. Verify services
make docker-ps

# 6. Test API
curl http://localhost:8000/health
```

**Expected Output:**
```json
{
  "status": "healthy",
  "environment": "production",
  "database": "connected",
  "redis": "connected"
}
```

---

## 🏗️ Architecture

### Service Stack

```
┌─────────────────────────────────────────────────┐
│          Docker Compose Network                 │
│            (gta_network - bridge)               │
├──────────────┬──────────────┬────────────────────┤
│   API        │   PostgreSQL │   Redis            │
│   (FastAPI)  │   (16-Alpine)│   (7-Alpine)       │
│   Port 8000  │   Port 5432  │   Port 6379        │
│   4 Workers  │   Data Vol   │   Data Vol         │
└──────────────┴──────────────┴────────────────────┘
```

### Components

| Component | Image | Version | Purpose |
|-----------|-------|---------|---------|
| **API** | python | 3.12-slim | FastAPI application |
| **PostgreSQL** | postgres | 16-alpine | Relational database |
| **Redis** | redis | 7-alpine | Caching & sessions |

### Build Strategy

**Multi-stage Dockerfile (Optimized)**
```
Stage 1 (base):        System deps, Python 3.12
Stage 2 (builder):     Virtual env, dependencies
Stage 3 (final):       Minimal runtime, non-root user
```

**Total Image Size:** ~270 MB (optimized)

---

## 📦 Installation

### Prerequisites

- Docker Desktop v4.0+ or Docker Engine + Docker Compose v2.0+
- 2GB available disk space
- Ports 8000, 5432, 6379 available

### Check Installation

```bash
# Verify Docker
docker --version
# Docker version 24.0+

# Verify Docker Compose
docker-compose --version
# Docker Compose version v2.20+
```

### Get Started

```bash
# Clone/navigate to project
cd /mnt/hackwrld/Projects/GTA/code_memoire

# All Docker files are in docker/ folder
ls -la docker/
```

---

## ⚙️ Configuration

### Environment Setup

**Step 1: Copy template**
```bash
cp docker/.env.docker .env
```

**Step 2: Edit .env with required values**
```bash
# Critical - MUST change from default
SECRET_KEY=your-super-secret-key-here-change-me
DB_PASSWORD=strong-password-here-change-me
SUPERADMIN_EMAIL=your-admin@example.com

# Optional - for email functionality
MAIL_USERNAME=your-smtp-user@gmail.com
MAIL_PASSWORD=your-app-specific-password

# Optional - for blockchain
RPC_URL=https://mainnet.infura.io/v3/YOUR-PROJECT-ID
CONTRACT_ADDRESS=0x...
```

### Environment Variables

#### Core Settings
```bash
ENVIRONMENT=docker          # or: local, staging, production
DEBUG=false                  # Set to true only in development
API_PORT=8000               # Container port
API_HOST=0.0.0.0            # Listen on all interfaces
```

#### Database
```bash
DATABASE_URL=postgresql+asyncpg://user:pass@postgres:5432/db
DB_USER=gta_user            # PostgreSQL user
DB_PASSWORD=gta_password    # PostgreSQL password (CHANGE!)
DB_NAME=gta_fintech         # Database name
DB_PORT=5432                # PostgreSQL port
```

#### Redis
```bash
REDIS_URL=redis://redis:6379
REDIS_PORT=6379
```

#### Security
```bash
SECRET_KEY=your-secret      # JWT signing key (CHANGE!)
ALGORITHM=HS256             # JWT algorithm
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

#### Email
```bash
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=app-password-not-account-password
MAIL_FROM=noreply@fintech.local
```

#### Blockchain
```bash
RPC_URL=http://localhost:8545      # Local or Infura/Alchemy
CONTRACT_ADDRESS=0xabcd1234...
ADMIN_PRIVATE_KEY=                 # For contract interactions
```

#### Logging
```bash
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR
```

---

## 🐳 Running Containers

### Start All Services

```bash
# Using Makefile (recommended)
make docker-up

# Or manually
docker-compose -f docker/docker-compose.yml up -d
```

### Build Custom Configuration

```bash
# Rebuild image
make docker-build

# Rebuild without cache
docker-compose -f docker/docker-compose.yml build --no-cache

# Build specific service
docker-compose -f docker/docker-compose.yml build api
```

### View Logs

```bash
# All services
make docker-logs

# Specific service
make docker-logs-api

# Follow new logs
docker-compose -f docker/docker-compose.yml logs -f api

# Last 50 lines
docker-compose -f docker/docker-compose.yml logs --tail=50 api
```

### Access Container Shell

```bash
# Interactive bash in API container
make docker-shell

# Run single command
docker-compose -f docker/docker-compose.yml exec api python -c "import sys; print(sys.version)"

# Run pytest in container
make docker-test
```

### Stop Containers

```bash
# Stop all containers
make docker-down

# Stop and remove volumes (clean slate)
make docker-clean

# Restart specific service
docker-compose -f docker/docker-compose.yml restart api
```

---

## 🛠️ Common Operations

### Database Operations

```bash
# Connect to PostgreSQL CLI
docker-compose -f docker/docker-compose.yml exec postgres psql -U gta_user -d gta_fintech

# Run SQL query
docker-compose -f docker/docker-compose.yml exec postgres psql -U gta_user -d gta_fintech -c "SELECT COUNT(*) FROM public.user;"

# Backup database
docker-compose -f docker/docker-compose.yml exec postgres pg_dump -U gta_user gta_fintech > backup.sql

# Restore database
docker-compose -f docker/docker-compose.yml exec postgres psql -U gta_user gta_fintech < backup.sql
```

### Redis Operations

```bash
# Connect to Redis CLI
docker-compose -f docker/docker-compose.yml exec redis redis-cli

# Check key count
docker-compose -f docker/docker-compose.yml exec redis redis-cli dbsize

# Flush all data
docker-compose -f docker/docker-compose.yml exec redis redis-cli flushall
```

### Run Migrations

```bash
# Create new migration
docker-compose -f docker/docker-compose.yml exec api alembic revision --autogenerate -m "Add new table"

# Apply migrations
docker-compose -f docker/docker-compose.yml exec api alembic upgrade head

# Downgrade migration
docker-compose -f docker/docker-compose.yml exec api alembic downgrade -1
```

### View Running Processes

```bash
# Show containers
make docker-ps

# Show detailed info
docker-compose -f docker/docker-compose.yml ps --all

# Show container resource usage
docker stats gta_fintech_api
```

---

## 🔍 Health Checks

### API Health

```bash
# HTTP health check
curl http://localhost:8000/health

# With verbose output
curl -v http://localhost:8000/health

# Check status endpoint
curl http://localhost:8000/status
```

### Database Health

```bash
# PostgreSQL readiness
docker-compose -f docker/docker-compose.yml exec postgres pg_isready -U gta_user

# Query test
docker-compose -f docker/docker-compose.yml exec postgres psql -U gta_user -d gta_fintech -c "SELECT NOW();"
```

### Redis Health

```bash
# Redis ping
docker-compose -f docker/docker-compose.yml exec redis redis-cli ping

# Check info
docker-compose -f docker/docker-compose.yml exec redis redis-cli INFO server
```

---

## 🐛 Troubleshooting

### Container Won't Start

**Problem:** API container exits immediately
```bash
# Check logs
make docker-logs-api

# Verify environment
docker-compose -f docker/docker-compose.yml exec api env | grep DATABASE
```

**Solution:** Verify .env file has correct DATABASE_URL and credentials match docker-compose.yml

### Port Already in Use

**Problem:** `Error: Port 8000 already in use`
```bash
# Find process using port
lsof -i :8000

# Kill process (replace PID)
kill -9 <PID>

# Or change port in .env
API_PORT=8001
```

### Database Connection Failed

**Problem:** API logs show "cannot connect to database"
```bash
# Check PostgreSQL is running
docker-compose -f docker/docker-compose.yml ps postgres

# Check PostgreSQL logs
docker-compose -f docker/docker-compose.yml logs postgres

# Verify network
docker network inspect docker_gta_network
```

**Solution:** Ensure postgres service is healthy (wait 10-15 seconds after startup)

### Out of Memory

**Problem:** Containers crash with OOM errors
```bash
# Check memory usage
docker stats

# Reduce API workers in docker/Dockerfile
# Change: CMD ["uvicorn", "main:app", "--workers", "2"]
```

### Volume Permission Issues

**Problem:** Cannot write to logs/models directories
```bash
# Fix permissions in container
docker-compose -f docker/docker-compose.yml exec api chmod -R 755 /app/logs /app/models

# Or recreate volumes
docker-compose -f docker/docker-compose.yml down -v
docker-compose -f docker/docker-compose.yml up -d
```

---

## 🚢 Production Deployment

### Security Hardening

**Before deploying:**

1. **Change all secrets**
   ```bash
   # Generate new SECRET_KEY
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   
   # Update .env with strong passwords
   SECRET_KEY=<generated-token>
   DB_PASSWORD=<strong-random-password>
   ```

2. **Enable HTTPS**
   - Use Nginx/Traefik reverse proxy
   - Enable SSL certificates (Let's Encrypt)
   - Force HTTPS redirect

3. **Configure firewall**
   - Expose only port 80/443 (API)
   - Keep 5432 (PostgreSQL) internal only
   - Keep 6379 (Redis) internal only

4. **Set environment to production**
   ```bash
   ENVIRONMENT=production
   DEBUG=false
   ```

### Scale to Multiple API Instances

```bash
# Scale API to 3 instances
docker-compose -f docker/docker-compose.yml up -d --scale api=3

# Use load balancer (Nginx) to distribute traffic
```

### Monitor Containers

```bash
# Real-time resource usage
docker stats

# Container logs with timestamps
docker-compose -f docker/docker-compose.yml logs --timestamps -f

# Export metrics
docker stats --no-stream --format "table {{.Container}}\t{{.MemUsage}}"
```

### Backup Strategy

```bash
# Backup database daily
docker-compose -f docker/docker-compose.yml exec postgres pg_dump -U gta_user gta_fintech | gzip > backup-$(date +%Y%m%d).sql.gz

# Backup Redis
docker-compose -f docker/docker-compose.yml exec redis redis-cli BGSAVE
docker cp gta_fintech_cache:/data/dump.rdb ./dump.rdb
```

### Disaster Recovery

```bash
# Stop containers
make docker-down

# Restore from backup
docker-compose -f docker/docker-compose.yml up -d postgres redis
sleep 10
cat backup.sql.gz | gunzip | docker-compose -f docker/docker-compose.yml exec -T postgres psql -U gta_user gta_fintech

# Start API
docker-compose -f docker/docker-compose.yml up -d api
```

---

## 📚 References

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Specification](https://docs.docker.com/compose/compose-file/)
- [Python Docker Best Practices](https://docs.docker.com/language/python/build-images/)
- [PostgreSQL Docker](https://hub.docker.com/_/postgres)
- [Redis Docker](https://hub.docker.com/_/redis)

---

## 💡 Tips & Best Practices

✅ **Do's:**
- Use `.dockerignore` to reduce build context
- Use multi-stage builds for optimization
- Keep images small (use slim/alpine bases)
- Run as non-root user for security
- Use environment variables for configuration
- Implement health checks
- Use volumes for persistent data
- Tag images with version numbers

❌ **Don'ts:**
- Don't run containers as root
- Don't hardcode secrets in Dockerfile
- Don't use `latest` tag in production
- Don't mount entire source tree in production
- Don't ignore container logs
- Don't forget to backup databases
- Don't use host network mode unnecessarily

---

**Last Updated:** July 2026  
**Docker Folder:** `/mnt/hackwrld/Projects/GTA/code_memoire/docker/`
