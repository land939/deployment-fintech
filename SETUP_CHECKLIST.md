# 🚀 GTA Fintech - Setup Checklist

## Prerequisites
- [ ] Python 3.12+ installed
- [ ] Git installed
- [ ] PostgreSQL 14+ (or use Docker)
- [ ] pip and venv available

## 1️⃣ Initial Setup

```bash
# Clone or navigate to project
cd /mnt/hackwrld/Projects/GTA/code_memoire

# Create virtual environment
python3.12 -m venv venv
source venv/bin/activate  # macOS/Linux
# or
.\venv\Scripts\activate  # Windows

# Upgrade pip
pip install --upgrade pip setuptools wheel
```

## 2️⃣ Install Dependencies

```bash
# Development mode with all dependencies
make dev-install

# Or manually
pip install -e ".[dev]"
```

## 3️⃣ Configure Environment

```bash
# Copy example environment
cp .env.example .env

# Edit .env with your settings (IMPORTANT!)
nano .env
```

**Required settings in .env:**
- `DATABASE_URL` - PostgreSQL connection string
- `SECRET_KEY` - JWT secret (min 32 chars)
- `SUPERADMIN_EMAIL` - Admin email
- `SUPERADMIN_PASSWORD` - Admin password
- `RPC_URL` - Blockchain RPC (e.g., http://127.0.0.1:7545)
- `MAIL_SERVER` - SMTP server (e.g., smtp.gmail.com)
- `MAIL_USERNAME` - SMTP username
- `MAIL_PASSWORD` - SMTP password

## 4️⃣ Setup Database

### Option A: Local PostgreSQL

```bash
# Create database
createdb -U postgres gta_fintech

# In .env set:
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/gta_fintech
```

### Option B: Docker PostgreSQL

```bash
# Start PostgreSQL
docker-compose up -d postgres

# Wait for health check
docker-compose logs postgres

# In .env set:
DATABASE_URL=postgresql+asyncpg://gta_user:gta_password@localhost:5432/gta_fintech
```

## 5️⃣ Initialize Database

```bash
# Create tables
python -c "
from config import get_settings
from database import init_db
import asyncio

async def setup():
    settings = get_settings()
    engine, session = await init_db(settings.database_url)
    await engine.dispose()

asyncio.run(setup())
"
```

## 6️⃣ Setup Pre-commit Hooks

```bash
# Install pre-commit
pre-commit install

# Run initial check
make pre-commit
```

## 7️⃣ Verify Setup

```bash
# Run all quality checks
make security

# Run tests
make test

# Check for type errors
make type-check
```

## 8️⃣ Start Development Server

```bash
# Development mode (auto-reload)
make run

# or
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Server will be available at:**
- 🌐 API: http://localhost:8000
- 📚 Swagger Docs: http://localhost:8000/docs
- 🔄 ReDoc: http://localhost:8000/redoc

## ✅ Verification Tests

### 1. Health Check
```bash
curl http://localhost:8000/health
```

Expected response:
```json
{"status": "operational", "timestamp": "2026-07-14T..."}
```

### 2. Status Endpoint
```bash
curl http://localhost:8000/status
```

Expected response includes database, blockchain, and ML model status.

### 3. Register User
```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "TestPassword123",
    "wallet_address": "0x742d35Cc6634C0532925a3b844Bc9e7595f42bE0"
  }'
```

### 4. Check Fraud
```bash
curl -X POST http://localhost:8000/fraud/check \
  -H "Content-Type: application/json" \
  -d '{"amount": 100.0, "hour_of_day": 14}'
```

## 🔧 Development Commands

```bash
# Format and lint code
make format
make lint

# Type checking
make type-check

# Security scan
make bandit

# All checks
make security

# Run tests with coverage
make test

# Clean build artifacts
make clean

# Show help
make help
```

## 🐳 Docker Deployment

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f api

# Run migrations
docker-compose exec api alembic upgrade head

# Stop services
docker-compose down
```

## 🛠️ Troubleshooting

### Database Connection Error
```
error: Could not connect to postgresql://...
```

**Solution:**
- Verify PostgreSQL is running
- Check DATABASE_URL in .env
- Ensure username/password are correct
- Check network connectivity

### ML Models Not Found
```
❌ Fraud model not found: ./models/fraud_detector.pkl
```

**Solution:**
- Generate models from fraud_detection_IA.ipynb
- Or copy from backup if available
- Check that models/ directory exists

### Port Already in Use
```
Address already in use ('::', 8000)
```

**Solution:**
```bash
# Find process on port 8000
lsof -i :8000

# Kill it
kill -9 <PID>

# Or use different port
uvicorn main:app --port 8001
```

### Pre-commit Hooks Failing

```bash
# Run and fix issues
make format

# Then commit again
git commit -m "..."
```

## 📊 Project Structure Quick Reference

```
config/           Configuration & settings
database/         Database models & initialization
services/         Business logic (ML, blockchain)
routers/          API endpoints
schemas/          Request/response validation
utils/            Utility functions
tests/            Unit & integration tests
models/           Pickled ML models
logs/             Application logs
main.py           FastAPI application
```

## 🔐 Security Checklist

- [ ] `.env` created and configured (not committed)
- [ ] `SECRET_KEY` changed to unique value
- [ ] Database password is strong
- [ ] MAIL_PASSWORD is app-specific (not main password)
- [ ] ADMIN_PRIVATE_KEY never hardcoded
- [ ] Pre-commit hooks installed
- [ ] Bandit security scan passes
- [ ] No secrets in git history

## 📝 Next Development Steps

1. **Create additional routers**: wallet/, optimization/
2. **Add comprehensive tests**: api/, integration tests
3. **Setup database migrations**: Alembic configuration
4. **Configure CI/CD**: GitHub Actions
5. **Add API authentication**: JWT middleware
6. **Setup monitoring**: Application insights, error tracking
7. **Add rate limiting**: Redis backend for prod
8. **Email integration**: Send reset tokens and alerts

## ✨ What's Ready

✅ FastAPI application setup
✅ Async PostgreSQL database
✅ ML fraud detection (31 features)
✅ JWT authentication flow
✅ Pre-commit quality checks
✅ Docker deployment config
✅ Comprehensive documentation
✅ Unit test framework
✅ GitHub Actions CI/CD
✅ Professional code structure

---

**Made with ❤️ by Arthur Nganou**
