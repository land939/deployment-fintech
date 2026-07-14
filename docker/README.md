# Docker Configuration for GTA Fintech Platform

This folder contains all Docker-related files for containerizing and running the GTA Fintech application.

## 📁 Files

- **Dockerfile** - Multi-stage Docker image with Python 3.12 slim base
- **docker-compose.yml** - Orchestration file for API, PostgreSQL, and Redis services
- **.dockerignore** - Files excluded from Docker build context
- **.env.docker** - Environment variables template for Docker
- **init.sql** - PostgreSQL initialization script
- **README.md** - This file

## 🚀 Quick Start

### Prerequisites
- Docker Desktop (v4.0+)
- Docker Compose (v2.0+)

### 1. Prepare Environment
```bash
# Copy docker env to project root
cp docker/.env.docker .env

# Or use directly with docker-compose
docker-compose -f docker/docker-compose.yml up
```

### 2. Start Services
```bash
# From project root, build and start all services
docker-compose -f docker/docker-compose.yml up -d

# Or with custom env file
docker-compose -f docker/docker-compose.yml --env-file docker/.env.docker up -d
```

### 3. Verify Services
```bash
# Check running containers
docker ps

# View logs
docker-compose -f docker/docker-compose.yml logs -f api

# Test API health
curl http://localhost:8000/health
```

### 4. Access Services

| Service | URL | Credentials |
|---------|-----|-------------|
| API | http://localhost:8000 | - |
| Swagger Docs | http://localhost:8000/docs | - |
| ReDoc | http://localhost:8000/redoc | - |
| PostgreSQL | localhost:5432 | gta_user / gta_password |
| Redis | localhost:6379 | - |

## 🔧 Common Commands

### Build Images
```bash
# Build API image
docker-compose -f docker/docker-compose.yml build api

# Rebuild without cache
docker-compose -f docker/docker-compose.yml build --no-cache api
```

### View Logs
```bash
# All services
docker-compose -f docker/docker-compose.yml logs -f

# Specific service
docker-compose -f docker/docker-compose.yml logs -f api

# Last 100 lines
docker-compose -f docker/docker-compose.yml logs --tail=100 api
```

### Stop Services
```bash
# Stop all services
docker-compose -f docker/docker-compose.yml stop

# Stop and remove containers
docker-compose -f docker/docker-compose.yml down

# Stop and remove volumes (clean slate)
docker-compose -f docker/docker-compose.yml down -v
```

### Execute Commands in Container
```bash
# Run bash in API container
docker-compose -f docker/docker-compose.yml exec api bash

# Run Python command
docker-compose -f docker/docker-compose.yml exec api python -c "print('Hello')"

# Run pytest
docker-compose -f docker/docker-compose.yml exec api pytest tests/
```

### Database Operations
```bash
# Connect to PostgreSQL
docker-compose -f docker/docker-compose.yml exec postgres psql -U gta_user -d gta_fintech

# Create database migration
docker-compose -f docker/docker-compose.yml exec api alembic revision --autogenerate -m "message"

# Run migrations
docker-compose -f docker/docker-compose.yml exec api alembic upgrade head
```

## 🔑 Environment Variables

### Required for Production
- `SECRET_KEY` - JWT secret (change from default!)
- `DATABASE_URL` - PostgreSQL connection string
- `REDIS_URL` - Redis connection string
- `SUPERADMIN_EMAIL` - Initial admin email

### Optional
- `RPC_URL` - Blockchain RPC endpoint
- `MAIL_SERVER` - SMTP server for email
- `MAIL_USERNAME` - SMTP username
- `MAIL_PASSWORD` - SMTP password
- `LOG_LEVEL` - Logging level (DEBUG, INFO, WARNING, ERROR)

## 🏥 Health Checks

Each service includes health checks:

```bash
# Check API health
curl http://localhost:8000/health

# Check PostgreSQL
docker-compose -f docker/docker-compose.yml exec postgres pg_isready -U gta_user

# Check Redis
docker-compose -f docker/docker-compose.yml exec redis redis-cli ping
```

## 📊 Performance Tuning

### PostgreSQL
- Default: 256MB RAM limit
- Modify in docker-compose.yml under postgres environment

### Redis
- Default: 512MB RAM limit
- Configure via docker-compose.yml volumes/redis

### API
- Default: 4 workers
- Modify `CMD` in Dockerfile for more/fewer workers

## 🔐 Security Notes

### Before Production
1. ✅ Change `SECRET_KEY` in .env
2. ✅ Change `DB_PASSWORD` for PostgreSQL
3. ✅ Configure MAIL credentials
4. ✅ Set proper `RPC_URL` for blockchain
5. ✅ Enable HTTPS with reverse proxy (Nginx/Traefik)
6. ✅ Set CORS_ORIGINS to specific domains

### Docker Security
- API runs as non-root user (appuser)
- Read-only models volume
- No secrets in Dockerfile
- Minimal base image (python:3.12-slim)

## 🐛 Troubleshooting

### API won't start
```bash
# Check logs
docker-compose -f docker/docker-compose.yml logs api

# Verify environment variables
docker-compose -f docker/docker-compose.yml exec api env | grep DATABASE
```

### Database connection failed
```bash
# Check PostgreSQL is running
docker-compose -f docker/docker-compose.yml ps postgres

# Verify credentials
docker-compose -f docker/docker-compose.yml exec postgres psql -U gta_user -d gta_fintech -c "SELECT 1;"
```

### Port already in use
```bash
# Find process using port
lsof -i :8000

# Change port in .env file
API_PORT=8001
```

## 📦 Container Images

### Base Image
- **python:3.12-slim** (141 MB)
  - Minimal Python environment
  - Alpine-like efficiency with better compatibility
  - Security patches included

### Other Images
- **postgres:16-alpine** (89 MB)
- **redis:7-alpine** (42 MB)

**Total image size: ~270 MB**

## 🚢 Production Deployment

### Docker Swarm
```bash
docker stack deploy -c docker-compose.yml gta-fintech
```

### Kubernetes
```bash
# Generate manifests from compose
docker-compose -f docker/docker-compose.yml config > k8s-manifest.yaml
```

### Scaling
```bash
# Scale API service
docker-compose -f docker/docker-compose.yml up -d --scale api=3
```

## 📚 References

- [Docker Docs](https://docs.docker.com/)
- [Docker Compose Docs](https://docs.docker.com/compose/)
- [Python in Docker Best Practices](https://docs.docker.com/language/python/build-images/)
