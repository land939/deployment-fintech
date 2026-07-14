"""GTA Fintech - Main FastAPI Application."""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import Settings, get_settings, validate_required_settings, setup_logging
from database import init_db
from services.ml import FraudDetectionService
from services.blockchain import BlockchainService
from schemas import HealthResponse, StatusResponse, ErrorResponse

logger = logging.getLogger(__name__)

# Global instances
settings: Settings = None
async_session_factory = None
fraud_service: FraudDetectionService = None
blockchain_service: BlockchainService = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan context manager for startup/shutdown."""
    global settings, async_session_factory, fraud_service, blockchain_service

    # Startup
    logger.info("=" * 60)
    logger.info("🚀 GTA Fintech Platform Starting...")
    logger.info("=" * 60)

    try:
        # Load settings
        settings = get_settings()
        validate_required_settings(settings)

        # Setup logging
        setup_logging(settings)

        # Initialize database
        logger.info("📦 Initializing database...")
        engine, async_session_factory = await init_db(settings.database_url)
        logger.info("✅ Database initialized")

        # Initialize ML service
        logger.info("🤖 Loading ML models...")
        fraud_service = FraudDetectionService(settings)
        model_info = fraud_service.get_model_info()
        logger.info(f"✅ ML Service ready: {model_info}")

        # Initialize Blockchain service
        logger.info("🔗 Connecting to blockchain...")
        blockchain_service = BlockchainService(settings)
        if blockchain_service.connected:
            logger.info("✅ Blockchain connected")
        else:
            logger.warning("⚠️  Blockchain not available")

        logger.info("✅ GTA Fintech Platform Ready!")
        logger.info("=" * 60)

        yield

    except Exception as e:
        logger.error(f"❌ Startup failed: {e}")
        raise
    finally:
        # Shutdown
        logger.info("🛑 GTA Fintech Platform Shutting Down...")
        if engine:
            await engine.dispose()
        logger.info("✅ Cleanup complete")


# Create FastAPI app
app = FastAPI(
    title="GTA Fintech API",
    description="Blockchain + AI Fraud Detection Platform",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS Middleware
if settings is None:
    _settings = get_settings()
else:
    _settings = settings

app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origins,
    allow_credentials=_settings.cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ════════════════════════════════════════════════════════════════
# Health & Status Endpoints
# ════════════════════════════════════════════════════════════════


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Health check endpoint."""
    from datetime import datetime

    return {
        "status": "operational",
        "timestamp": datetime.utcnow(),
    }


@app.get("/status", response_model=StatusResponse, tags=["Status"])
async def get_status():
    """Get application status."""
    return {
        "app_version": "2.0.0",
        "environment": settings.environment,
        "database": {"connected": True},  # Add real DB check
        "blockchain": blockchain_service.get_network_info() if blockchain_service else {},
        "ml_models": fraud_service.get_model_info() if fraud_service else {},
    }


# ════════════════════════════════════════════════════════════════
# Error Handlers
# ════════════════════════════════════════════════════════════════


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle general exceptions."""
    logger.error(f"❌ Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc) if settings.debug else "An error occurred",
        },
    )


@app.exception_handler(ValueError)
async def value_error_handler(request, exc):
    """Handle value errors."""
    logger.warning(f"⚠️  Value error: {exc}")
    return JSONResponse(
        status_code=400,
        content={"error": "Invalid request", "detail": str(exc)},
    )


if __name__ == "__main__":
    import uvicorn

    # Load settings before running
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
