"""Application principale FastAPI — GTA Fintech."""

import logging
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select

from config import get_settings, setup_logging, validate_required_settings
from database import init_db, set_session_factory
from database.bootstrap import ensure_superadmin
from database.models import Transaction
from routers import auth, disputes, fraud, pages, superadmin, transactions, wallet
from schemas import HealthResponse, StatusResponse
from services.blockchain import BlockchainService, set_blockchain_service
from services.ml import FraudDetectionService, set_fraud_service
from services.rates import get_ftk_eth_rate
from prometheus_fastapi_instrumentator import Instrumentator

logger = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parent

settings = None
async_session_factory = None
fraud_service: FraudDetectionService | None = None
blockchain_service: BlockchainService | None = None
engine = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Démarrage / arrêt de l'application."""
    global settings, async_session_factory, fraud_service, blockchain_service, engine

    settings = get_settings()
    validate_required_settings(settings)
    setup_logging(settings)

    engine, async_session_factory = await init_db(settings.database_url)
    set_session_factory(async_session_factory)
    await ensure_superadmin(async_session_factory, settings)

    try:
        fraud_service = FraudDetectionService(settings)
        set_fraud_service(fraud_service)
        logger.info("Service ML prêt: %s", fraud_service.get_model_info())
    except Exception as e:
        fraud_service = None
        set_fraud_service(None)
        logger.warning("Modèles ML indisponibles: %s", e)

    blockchain_service = BlockchainService(settings)
    set_blockchain_service(blockchain_service)
    logger.info(
        "Blockchain %s",
        "connectée" if blockchain_service.connected else "indisponible",
    )
    logger.info("Plateforme GTA Fintech prête")
    yield

    set_fraud_service(None)
    set_blockchain_service(None)
    if engine:
        await engine.dispose()


app = FastAPI(
    title="GTA Fintech",
    description="Blockchain + détection de fraude IA",
    version="2.0.0",
    lifespan=lifespan,
)

# Instrument the FastAPI app for Prometheus monitoring
Instrumentator().instrument(app).expose(app)

_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origins,
    allow_credentials=_settings.cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

static_dir = ROOT / "static"
if static_dir.is_dir():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

app.include_router(pages.router)
app.include_router(auth.router)
app.include_router(fraud.router)
app.include_router(transactions.router)
app.include_router(disputes.router)
app.include_router(wallet.router)
app.include_router(superadmin.router)


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    return {"status": "operational", "timestamp": datetime.utcnow()}


@app.get("/status", response_model=StatusResponse, tags=["Status"])
async def get_status():
    """Statut pour le badge UI."""
    chain_info = blockchain_service.get_network_info() if blockchain_service else {}
    connected = bool(blockchain_service and blockchain_service.connected)
    chain_id = chain_info.get("chain_id") if isinstance(chain_info, dict) else None

    total_tx = 0
    if async_session_factory is not None:
        try:
            async with async_session_factory() as session:
                total_tx = (
                    await session.execute(select(func.count()).select_from(Transaction))
                ).scalar_one()
        except Exception:
            total_tx = 0

    return {
        "app_version": "2.0.0",
        "environment": settings.environment if settings else "unknown",
        "blockchain_connected": connected,
        "chain_id": chain_id,
        # Infos nécessaires au front pour MetaMask + conversion FTK/ETH
        "token_address": settings.token_address if settings else None,
        "ftk_eth_rate": get_ftk_eth_rate(settings) if settings else None,
        "ia_model_loaded": fraud_service is not None,
        "total_transactions": total_tx,
    }


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.error("Exception non gérée: %s", exc)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Erreur interne",
            "detail": str(exc) if settings and settings.debug else "Une erreur est survenue",
        },
    )


@app.exception_handler(ValueError)
async def value_error_handler(request, exc):
    return JSONResponse(
        status_code=400,
        content={"error": "Requête invalide", "detail": str(exc)},
    )


if __name__ == "__main__":
    import uvicorn

    cfg = get_settings()
    setup_logging(cfg)
    uvicorn.run(
        "main:app",
        host=cfg.api_host,
        port=cfg.api_port,
        workers=cfg.api_workers if not cfg.debug else 1,
        reload=cfg.debug,
        log_level=cfg.api_log_level,
    )
