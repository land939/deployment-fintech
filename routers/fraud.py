"""Fraud detection routes."""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from config import Settings, get_settings
from database import get_session
from database.models import FraudAlert, Transaction
from services.ml import FraudDetectionService
from schemas import FraudCheckRequest, FraudCheckResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/fraud", tags=["Fraud Detection"])


@router.post("/check", response_model=FraudCheckResponse)
async def check_fraud(
    request: FraudCheckRequest,
    settings: Settings = Depends(get_settings),
):
    """Check transaction for fraud using ML model."""
    if not settings.enable_ml_fraud_detection:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Fraud detection service is disabled",
        )

    try:
        # Initialize ML service
        ml_service = FraudDetectionService(settings)

        # Prepare features (all 31)
        transaction_data = {"Amount": request.amount}

        if request.time is not None:
            transaction_data["Time"] = request.time
        elif request.hour_of_day is not None:
            transaction_data["Time"] = request.hour_of_day * 3600

        # Add optional features
        if request.features:
            transaction_data.update(request.features)

        # Get prediction
        result = ml_service.predict_fraud(transaction_data)

        if "error" in result:
            logger.error(f"❌ Fraud prediction error: {result['error']}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Fraud detection failed",
            )

        logger.info(
            f"🔍 Fraud check: amount={request.amount}, "
            f"risk={result['risk_level']}, blocked={result['blocked']}"
        )

        return FraudCheckResponse(**result)

    except Exception as e:
        logger.error(f"❌ Fraud detection error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Fraud detection service error",
        )


@router.get("/reports")
async def get_fraud_reports(
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_session),
):
    """Get all fraud alerts (admin only)."""
    result = await db.execute(
        select(FraudAlert)
        .order_by(FraudAlert.created_at.desc())
        .offset(skip)
        .limit(limit)
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


@router.get("/check/{address}")
async def check_address_fraud(
    address: str,
    db: AsyncSession = Depends(get_session),
):
    """Get fraud history for an address."""
    result = await db.execute(
        select(FraudAlert)
        .where(FraudAlert.suspect_address == address)
        .order_by(FraudAlert.created_at.desc())
        .limit(10)
    )
    alerts = result.scalars().all()

    if not alerts:
        return {
            "address": address,
            "fraud_count": 0,
            "alerts": [],
        }

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
