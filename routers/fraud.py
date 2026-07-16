"""Routes détection de fraude."""

import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from config import SettingsDep
from database import DbSession
from database.models import FraudAlert
from schemas import FraudCheckRequest, FraudCheckResponse
from services.ml import get_fraud_service
from services.ml.features import FEATURE_COLS

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/fraud", tags=["Fraud Detection"])


@router.post("/check", response_model=FraudCheckResponse)
async def check_fraud(
    request: FraudCheckRequest,
    settings: SettingsDep,
):
    """Vérifie une transaction via le modèle ML (11 features FTK)."""
    if not settings.enable_ml_fraud_detection:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service de détection de fraude désactivé",
        )

    ml_service = get_fraud_service()
    if ml_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Modèles ML indisponibles",
        )

    try:
        transaction_data = dict.fromkeys(FEATURE_COLS, 0.0)
        transaction_data["amount"] = float(request.amount)
        hour = request.hour if request.hour is not None else request.hour_of_day
        if hour is not None:
            transaction_data["hour"] = float(hour)
        else:
            transaction_data["hour"] = float(datetime.now().hour)
        transaction_data["day_of_week"] = float(datetime.utcnow().weekday())

        if request.features:
            for k, v in request.features.items():
                if k in transaction_data:
                    transaction_data[k] = float(v)

        result = ml_service.predict_fraud(transaction_data)

        if "error" in result:
            logger.error("Erreur prédiction: %s", result["error"])
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Échec de la détection de fraude",
            )

        return FraudCheckResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Erreur service fraude: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur du service de détection de fraude",
        ) from e


@router.get("/reports")
async def get_fraud_reports(db: DbSession, skip: int = 0, limit: int = 50):
    """Liste des alertes fraude."""
    result = await db.execute(
        select(FraudAlert).order_by(FraudAlert.created_at.desc()).offset(skip).limit(limit)
    )
    alerts = result.scalars().all()

    return {
        "total": len(alerts),
        "alerts": [
            {
                "id": alert.id,
                "suspect": alert.suspect_address,
                "amount": alert.amount,
                "risk_score": alert.risk_score,
                "risk_level": alert.risk_level,
                "blocked": alert.blocked,
                "created_at": alert.created_at,
            }
            for alert in alerts
        ],
    }


@router.get("/list")
async def list_fraud(db: DbSession, limit: int = 50):
    """Alias UI pour /fraud/reports."""
    return await get_fraud_reports(db, skip=0, limit=limit)


@router.get("/check/{address}")
async def check_address_fraud(address: str, db: DbSession):
    """Historique fraude pour une adresse."""
    result = await db.execute(
        select(FraudAlert)
        .where(FraudAlert.suspect_address == address)
        .order_by(FraudAlert.created_at.desc())
        .limit(10)
    )
    alerts = result.scalars().all()

    if not alerts:
        return {"address": address, "fraud_count": 0, "alerts": []}

    high_risk_count = sum(1 for a in alerts if a.risk_level in ["HIGH", "CRITICAL"])

    return {
        "address": address,
        "fraud_count": len(alerts),
        "high_risk_count": high_risk_count,
        "latest_risk_score": alerts[0].risk_score if alerts else 0,
        "alerts": [
            {
                "id": a.id,
                "amount": a.amount,
                "risk_score": a.risk_score,
                "risk_level": a.risk_level,
                "blocked": a.blocked,
                "created_at": a.created_at,
            }
            for a in alerts
        ],
    }
