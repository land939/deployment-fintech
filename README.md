# GTA Fintech - Blockchain + AI Fraud Detection Platform

![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue)
![FastAPI](https://img.shields.io/badge/framework-FastAPI-009688)
![PostgreSQL](https://img.shields.io/badge/database-PostgreSQL-316192)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

## 🎯 Features

- **🔗 Blockchain Integration**: Web3.py with ERC-20 tokens + fraud registry smart contracts
- **🤖 AI Fraud Detection**: Machine Learning (XGBoost + RandomForest) with **31 features**
- **💰 Transaction Optimization**: Gas optimization for blockchain transactions
- **🛡️ Security**: JWT authentication, rate limiting, account lockout, audit logging
- **📧 Email Verification**: SMTP-based password reset with token validation
- **⚡ Async/Await**: FastAPI with async PostgreSQL (asyncpg)
- **✅ Type Safety**: Full type hints + MyPy validation
- **🔍 Pre-commit Checks**: Ruff + Bandit + MyPy + Pylint

## 🚀 Quick Start

### Prerequisites

- Python 3.12+
- PostgreSQL 14+
- Git

### Installation

```bash
# Clone repository
git clone https://github.com/nganouarthur9-ing/code_memoire.git
cd code_memoire

# Create virtual environment
python3.12 -m venv venv
source venv/bin/activate  # macOS/Linux
# or
.\venv\Scripts\activate  # Windows

# Install dependencies
make dev-install

# Configure environment
cp .env.example .env
# Edit .env with your settings

# Initialize database
make setup-db

# Run pre-commit checks
make pre-commit

# Start server
make run
```

The API will be available at `http://localhost:8000`
- 📚 **Swagger Docs**: http://localhost:8000/docs
- 🔄 **ReDoc**: http://localhost:8000/redoc

## 📋 Project Structure

```
gta-fintech/
├── config/                 # Configuration & settings
│   ├── settings.py        # Pydantic settings with validation
│   ├── logging.py         # Logging configuration
│   └── __init__.py
├── database/              # Database layer
│   ├── models.py          # SQLAlchemy ORM models
│   └── __init__.py
├── services/              # Business logic
│   ├── ml/               # Machine learning service
│   │   ├── __init__.py  # FraudDetectionService with 31 features
│   │   └── ...
│   └── blockchain/       # Blockchain interactions
│       ├── __init__.py  # Web3 service
│       └── ...
├── routers/               # API endpoints (auth, transactions, fraud, etc.)
├── schemas/               # Pydantic request/response schemas
├── utils/                 # Utilities (validation, JWT, email)
├── templates/             # HTML templates
├── models/                # Pickled ML models
├── migrations/            # Alembic database migrations
├── tests/                 # Unit & integration tests
├── main.py                # FastAPI application entry point
├── pyproject.toml         # Dependencies & tool config
├── .pre-commit-config.yaml # Pre-commit hooks
├── .bandit                # Bandit security config
├── .env.example           # Environment template
├── Makefile               # Development commands
└── README.md              # This file
```

## 🔧 Development

### Code Quality

```bash
# Format code
make format

# Lint code
make lint

# Type checking
make type-check

# Security scan
make bandit

# All checks
make security
```

### Testing

```bash
# Run all tests
make test

# Run specific test
pytest tests/test_auth.py -v

# Coverage report
pytest --cov=. --cov-report=html
```

### Database

```bash
# Create migrations
alembic revision --autogenerate -m "Add new column"

# Apply migrations
alembic upgrade head

# Rollback migration
alembic downgrade -1
```

## 🐳 Docker Deployment

```bash
# Start PostgreSQL + Redis
docker-compose up -d

# Run migrations
docker-compose exec api alembic upgrade head

# View logs
docker-compose logs -f api

# Stop services
docker-compose down
```

## 🔐 Security Features

- ✅ **Password Hashing**: PBKDF2-SHA256 (600k iterations)
- ✅ **JWT Tokens**: HS256 with configurable expiry
- ✅ **Rate Limiting**: Per-minute limits on authentication endpoints
- ✅ **Account Lockout**: 5 failed login attempts → 15 min lockout
- ✅ **Audit Logging**: All security events logged and stored
- ✅ **CORS Protection**: Configurable origins
- ✅ **Security Headers**: X-Content-Type-Options, X-Frame-Options, etc.
- ✅ **Bandit Scanning**: Automated security checks in pre-commit

## 🤖 ML Models

The fraud detection service uses **31 features**:
- V1-V28: PCA-transformed transaction features
- Amount: Transaction amount
- Time/Hour: Temporal features

### Model Performance

- **Algorithm**: RandomForest + XGBoost ensemble
- **Training Data**: 284,807 transactions
- **Fraud Rate**: 0.17% (492 frauds)
- **Rebalancing**: SMOTE for imbalanced data
- **Features**: All 31 features passed to model

### Risk Levels

| Probability | Risk Level | Action |
|-------------|-----------|--------|
| < 0.30 | LOW | ✅ Approved |
| 0.30 - 0.60 | MEDIUM | ⚠️ Review |
| 0.60 - 0.85 | HIGH | 🚫 Blocked |
| ≥ 0.85 | CRITICAL | 🚫 Blocked + Alert |

## 🔗 Blockchain

### Smart Contracts

1. **FintechToken (ERC-20)**
   - Symbol: FTK
   - 1% auto-burn on transfers
   - Blacklist functionality

2. **FraudRegistry**
   - Immutable fraud report storage
   - On-chain risk scores
   - Oracle-based updates from Python backend

3. **TransactionOptimizer**
   - Gas price estimation
   - Transaction cost optimization

### Configuration

Set these in `.env`:
```bash
RPC_URL=http://127.0.0.1:7545                    # Ganache local
TOKEN_ADDRESS=0x...                              # Deployed FintechToken
REGISTRY_ADDRESS=0x...                           # Deployed FraudRegistry
OPTIMIZER_ADDRESS=0x...                          # Deployed TransactionOptimizer
ADMIN_ADDRESS=0x...                              # Admin wallet
ADMIN_PRIVATE_KEY=0x...                          # Admin private key
```

## 📊 API Endpoints

### Health & Status
- `GET /health` - Health check
- `GET /status` - Application status

### Authentication
- `POST /auth/register` - User registration
- `POST /auth/login` - User login
- `POST /auth/forgot-password` - Password reset request
- `POST /auth/reset-password` - Password reset with token

### Transactions
- `GET /transactions/recent` - Get recent transactions
- `GET /transactions/all` - Get all transactions (admin)
- `POST /transactions/send` - Send transaction with fraud check

### Fraud Detection
- `GET /fraud/check/{address}` - Get fraud risk for address
- `GET /fraud/reports` - Get fraud reports
- `GET /fraud/list` - List all fraud alerts

### Wallet
- `GET /wallet/balance/{address}` - Get token balance

### Super Admin
- `GET /superadmin/api/stats` - Platform statistics
- `GET /superadmin/api/transactions` - All transactions
- `GET /superadmin/api/alerts` - All fraud alerts
- `GET /superadmin/api/users` - All users

## 🐛 Troubleshooting

### Blockchain Not Connecting

```
❌ Connexion blockchain : False
```

**Solution**: Ensure Ganache is running on the configured RPC_URL:
```bash
ganache --host 127.0.0.1 --port 7545
```

### ML Models Not Loading

```
❌ Fraud model not found: ./models/fraud_detector.pkl
```

**Solution**: Regenerate models from `fraud_detection_IA.ipynb`:
```bash
jupyter notebook fraud_detection_IA.ipynb
# Run all cells to regenerate pickled models
```

### Email Not Sending

```
❌ Échec envoi email
```

**Solution**: Configure Gmail App Password:
1. Enable 2FA on Google account
2. Generate app-specific password
3. Set `MAIL_PASSWORD` in `.env`

## 📈 Performance Optimization

- ✅ Async database queries with asyncpg
- ✅ Connection pooling (20 connections)
- ✅ Query indexing on frequent fields
- ✅ JWT caching
- ✅ ML model pre-loading
- ✅ Rate limiting for API protection

## 🔄 CI/CD

GitHub Actions workflow (`.github/workflows/ci.yml`):
- ✅ Ruff linting
- ✅ MyPy type checking
- ✅ Bandit security scan
- ✅ Pytest with coverage
- ✅ Docker build

## 📝 License

MIT License - See LICENSE file for details

## 👥 Contributors

- **Arthur Nganou** - Initial development

## 📞 Support

For issues, questions, or contributions:
- GitHub Issues: https://github.com/nganouarthur9-ing/code_memoire/issues
- Email: dev@gta-fintech.local

---

**Made with ❤️ for the GTA-IT Fintech Ecosystem**
