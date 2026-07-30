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
| `database/` | Modèles SQLAlchemy async (SQLite local / PostgreSQL Docker) |
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
- Docker (optionnel — PostgreSQL + API conteneurisés)
- Ganache / nœud Ethereum (optionnel)

### Installation

```bash
git clone https://github.com/nganouarthur9-ing/code_memoire.git
cd code_memoire

python3.12 -m venv venv
source venv/bin/activate

pip install -e ".[dev]"
# ou: pip install -r requirements-dev.txt
cp .env.example .env   # puis renseigner les secrets
```

### Lancer l'API + UI (sans Docker)

Par défaut `.env` utilise **SQLite** (`./gta_fintech.db`) — aucun Postgres requis.

```bash
uvicorn main:app --reload --host 127.0.0.1 --port 8765
# ou
make run
```

- UI : http://127.0.0.1:8765/
- Docs OpenAPI : http://127.0.0.1:8765/docs

### Lancer avec Docker (PostgreSQL, Redis + Monitoring)

Le fichier Compose orchestre l'API, la base de données PostgreSQL, le cache Redis, ainsi que toute la pile de supervision (Prometheus, Grafana, Node-Exporter, Postgres-Exporter, Redis-Exporter).

```bash
# Copier les variables d'environnement Docker au besoin
cp docker/.env.docker .env

# Lancer tous les services en arrière-plan
docker compose -f docker/docker-compose.yml up -d
```

### URLs d'accès & Supervision

| Service / Endpoint | URL | Identifiants / Description |
|---|---|---|
| **API Web (Fintech)** | http://127.0.0.1:8000/ | Application principale (Français) |
| **Documentation API** | http://127.0.0.1:8000/docs | Swagger UI de l'API FastAPI |
| **Endpoint Métriques** | http://127.0.0.1:8000/metrics | Métriques au format Prometheus |
| **Prometheus Server** | http://127.0.0.1:9090/ | Visualisation des targets & alertes |
| **Grafana Dashboards** | http://127.0.0.1:3000/ | Supervision riche. Login: `admin` / `admin` |

### Alertes Prometheus actives

1. **ApiDown** : L'API ne répond plus (`up{job="api"} == 0`).
2. **PostgresDown** : PostgreSQL est injoignable (`pg_up == 0`).
3. **DiskSpaceRunningLow** : Espace disque racine disponible < 20% (utilisation > 80%).

### Dashboards pré-configurés (Grafana)

- **GTA Fintech - Host Metrics** : Consommation CPU, Mémoire RAM, Espace Disque.
- **GTA Fintech - Services Status** : État de santé de l'API, de la base Postgres, de Redis, et débit de requêtes.

### Tests

```bash
make test
# ou
python -m pytest tests/ -v --cov=. --cov-report=html
```

## Configuration

Les secrets vivent dans `.env` (jamais versionné) :

```
DATABASE_URL=sqlite+aiosqlite:///./gta_fintech.db   # local ; Postgres via Docker
SECRET_KEY=
SUPERADMIN_EMAIL=
SUPERADMIN_PASSWORD=
RPC_URL=                 # Ganache : http://127.0.0.1:7545
ADMIN_ADDRESS=
ADMIN_PRIVATE_KEY=       # NE JAMAIS COMMITER
TOKEN_ADDRESS=
REGISTRY_ADDRESS=
OPTIMIZER_ADDRESS=
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
