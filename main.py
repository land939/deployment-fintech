"""Application principale FastAPI — GTA Fintech."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select

from config import Settings, get_settings, setup_logging, validate_required_settings
from database import init_db, set_session_factory
from database.bootstrap import ensure_superadmin
from database.models import Transaction
from routers import auth, fraud, pages, superadmin, transactions
from schemas import HealthResponse, StatusResponse
from services.blockchain import BlockchainService
from services.ml import FraudDetectionService

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent

settings: Settings | None = None
async_session_factory = None
fraud_service: FraudDetectionService | None = None
blockchain_service: BlockchainService | None = None
engine = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Démarrage / arrêt de l'application."""
    global settings, async_session_factory, fraud_service, blockchain_service, engine

    logger.info("=" * 60)
    logger.info("Démarrage plateforme GTA Fintech...")
    logger.info("=" * 60)

    try:
        settings = get_settings()
        validate_required_settings(settings)
        setup_logging(settings)

        logger.info("Initialisation base de données...")
        engine, async_session_factory = await init_db(settings.database_url)
        set_session_factory(async_session_factory)
        await ensure_superadmin(async_session_factory, settings)
        logger.info("Base de données prête")

        logger.info("Chargement modèles ML...")
        try:
            fraud_service = FraudDetectionService(settings)
            logger.info("Service ML prêt: %s", fraud_service.get_model_info())
        except Exception as e:
            fraud_service = None
            logger.warning("Modèles ML indisponibles: %s", e)

        logger.info("Connexion blockchain...")
        blockchain_service = BlockchainService(settings)
        if blockchain_service.connected:
            logger.info("Blockchain connectée")
        else:
            logger.warning("Blockchain indisponible")

        logger.info("Plateforme GTA Fintech prête")
        logger.info("=" * 60)
        yield

    except Exception as e:
        logger.error("Échec démarrage: %s", e)
        raise
    finally:
        logger.info("Arrêt plateforme GTA Fintech...")
        if engine:
            await engine.dispose()
        logger.info("Nettoyage terminé")


app = FastAPI(
    title="GTA Fintech",
    description="Blockchain + détection de fraude IA",
    version="2.0.0",
    lifespan=lifespan,
)

_settings = get_settings() if settings is None else settings

app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origins,
    allow_credentials=_settings.cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Assets UI (option A : StaticFiles + Jinja2 dans le même serveur)
static_dir = ROOT / "static"
if static_dir.is_dir():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

app.include_router(pages.router)
app.include_router(auth.router)
app.include_router(fraud.router)
app.include_router(transactions.router)
app.include_router(superadmin.router)


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    from datetime import datetime

    return {"status": "operational", "timestamp": datetime.utcnow()}


@app.get("/status", response_model=StatusResponse, tags=["Status"])
async def get_status():
    """Statut pour le badge UI + détail technique."""
    chain_info = blockchain_service.get_network_info() if blockchain_service else {}
    connected = bool(blockchain_service and getattr(blockchain_service, "connected", False))
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
        "ia_model_loaded": fraud_service is not None,
        "total_transactions": total_tx,
        "database": {"connected": async_session_factory is not None},
        "blockchain": chain_info,
        "ml_models": fraud_service.get_model_info() if fraud_service else {},
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
    logger.warning("Erreur de valeur: %s", exc)
    return JSONResponse(
        status_code=400,
        content={"error": "Requête invalide", "detail": str(exc)},
    )


if __name__ == "__main__":
    import uvicorn

    _settings = get_settings()
    setup_logging(_settings)
    uvicorn.run(
        "main:app",
        host=_settings.api_host,
        port=_settings.api_port,
        workers=_settings.api_workers if not _settings.debug else 1,
        reload=_settings.debug,
        log_level=_settings.api_log_level,
    )
