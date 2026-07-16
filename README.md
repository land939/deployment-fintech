# GTA-IT Fintech — Détection de fraude par IA + Blockchain

Plateforme combinant une API **FastAPI**, un modèle de machine learning
(détection de fraude FTK) et des smart contracts Solidity (traçabilité
on-chain), autour d'un token utilitaire **FTK**.

## Architecture

| Composant | Rôle |
|---|---|
| `main.py` | Application FastAPI : API REST + pages Jinja2 + fichiers statiques |
| `routers/` | Routes auth, transactions, fraude, pages UI, superadmin |
| `services/ml/` | Détection de fraude (11 features calculables en production) |
| `services/blockchain/` | Intégration Web3 (token, registre, optimisation) |
| `database/` | Modèles SQLAlchemy async (PostgreSQL) |
| `FintechToken.sol` | Token ERC-20 « FTK » avec burn, blacklist et pause |
| `FraudRegistry.sol` | Registre on-chain des fraudes détectées par l'IA |
| `TransactionOptimizer.sol` | Paramètres d'optimisation on-chain |
| `train_fraud_model.py` | Dataset synthétique FTK + entraînement XGBoost |
| `models/` | Artefacts ML (`fraud_detector.pkl`, `scaler.pkl`, `feature_columns.json`) |
| `templates/` + `static/` | Interface web (dashboard, superadmin, auth) |
| `docker/` | Conteneurisation (Dockerfile + Compose v2) |

Flux principal : une transaction soumise est analysée par le modèle IA →
si le risque est élevé, elle est **bloquée**, peut être enregistrée dans le
`FraudRegistry` on-chain, et une alerte est accessible au super administrateur.

## Features ML (11 colonnes FTK)

Contrairement à un modèle entraîné sur le dataset Kaggle `creditcard`
(features PCA V1–V28 non calculables en prod), le modèle actuel utilise :

- `amount`, `hour`, `day_of_week`, `account_age_days`
- `tx_count_1h`, `tx_count_24h`, `amount_avg_ratio`
- `seconds_since_last_tx`, `is_new_receiver`
- `unique_receivers_24h`, `past_fraud_count`

Réentraînement : `python train_fraud_model.py`

## Démarrage rapide

### Prérequis

- Python 3.12+
- PostgreSQL 14+ (ou SQLite async pour les tests)
- Docker (optionnel)
- Ganache / nœud Ethereum (optionnel)

### Installation

```bash
git clone https://github.com/nganouarthur9-ing/code_memoire.git
cd code_memoire

python3.12 -m venv venv
source venv/bin/activate

pip install -e ".[dev]"
cp .env.example .env   # puis renseigner les secrets
```

### Lancer l'API + UI

```bash
make run
# ou
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

- UI : http://127.0.0.1:8000/
- Docs OpenAPI : http://127.0.0.1:8000/docs

### Tests

```bash
make test
# ou
python -m pytest tests/ -v --cov=. --cov-report=html
```

### Docker

```bash
make docker-build
make docker-up
```

## Configuration

Les secrets vivent dans `.env` (jamais versionné) :

```
DATABASE_URL=
SECRET_KEY=
SUPERADMIN_EMAIL=
SUPERADMIN_PASSWORD=
RPC_URL=                 # Ganache : http://127.0.0.1:7545
ADMIN_ADDRESS=
ADMIN_PRIVATE_KEY=       # NE JAMAIS COMMITER
TOKEN_ADDRESS=
REGISTRY_ADDRESS=
OPTIMIZER_ADDRESS=
JWT_SECRET=              # ou SECRET_KEY
MAIL_SERVER=
MAIL_PORT=
MAIL_USERNAME=
MAIL_PASSWORD=
```

## Structure du dépôt

```
code_memoire/
├── main.py
├── routers/          # auth, fraud, transactions, pages, superadmin
├── services/         # ml, blockchain
├── database/         # modèles async
├── schemas/          # Pydantic
├── config/           # settings + logging
├── templates/        # Jinja2 (FR)
├── static/           # CSS/JS/charts
├── models/           # pickles ML
├── docker/           # compose + Dockerfile
├── tests/
└── train_fraud_model.py
```

## Licence

MIT — Équipe GTA-IT
