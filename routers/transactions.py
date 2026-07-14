"""Transactions routes."""

import logging
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from config import Settings, get_settings
from database import get_session
from database.models import Transaction, User
from services.ml import FraudDetectionService
from schemas import TransactionRequest, TransactionResponse
from utils import is_valid_wallet

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/transactions", tags=["Transactions"])


@router.post("/send", response_model=TransactionResponse)
async def send_transaction(
    request: TransactionRequest,
    db: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    """Send a transaction with fraud detection."""
    # Validate receiver
    if not is_valid_wallet(request.receiver):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid receiver wallet address",
        )

    if request.amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Amount must be positive",
        )

    # Get current user (would come from JWT token in real app)
    # For now, use first user for demo
    result = await db.execute(select(User).limit(1))
    user = result.scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    # Run fraud detection
    ml_service = FraudDetectionService(settings)
    fraud_features = request.features or {
        "Amount": request.amount,
        "Time": datetime.utcnow().hour * 3600,
    }
    fraud_result = ml_service.predict_fraud(fraud_features)

    # Create transaction record
    tx_id = str(uuid.uuid4())
    transaction = Transaction(
        id=tx_id,
        user_id=user.id,
        sender=user.wallet_address,
        receiver=request.receiver,
        amount=request.amount,
        risk_score=fraud_result.get("risk_score", 0),
        risk_level=fraud_result.get("risk_level", "UNKNOWN"),
        blocked=fraud_result.get("blocked", False),
        status="pending" if not fraud_result.get("blocked") else "blocked",
    )

    db.add(transaction)
    await db.commit()

    logger.info(
        f"💰 Transaction created: {tx_id} | amount={request.amount} | "
        f"risk={fraud_result.get('risk_level')}"
    )

    return TransactionResponse(
        id=tx_id,
        sender=user.wallet_address,
        receiver=request.receiver,
        amount=request.amount,
        status=transaction.status,
        risk_score=fraud_result.get("risk_score", 0),
        risk_level=fraud_result.get("risk_level", "UNKNOWN"),
        blocked=fraud_result.get("blocked", False),
        created_at=transaction.created_at,
    )


@router.get("/recent")
async def get_recent_transactions(
    limit: int = 20,
    db: AsyncSession = Depends(get_session),
):
    """Get recent transactions."""
    result = await db.execute(
        select(Transaction)
        .order_by(Transaction.created_at.desc())
        .limit(limit)
    )
    transactions = result.scalars().all()

    return {
        "total": len(transactions),
        "transactions": [
            {
                "id": tx.id,
                "sender": tx.sender,
                "receiver": tx.receiver,
                "amount": tx.amount,
                "status": tx.status,
                "risk_level": tx.risk_level,
                "blocked": tx.blocked,
                "created_at": tx.created_at,
            }
            for tx in transactions
        ],
    }


@router.get("/all")
async def get_all_transactions(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_session),
):
    """Get all transactions (admin)."""
    result = await db.execute(
        select(Transaction)
        .order_by(Transaction.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    transactions = result.scalars().all()

    # Get stats
    blocked_count = sum(1 for tx in transactions if tx.blocked)
    high_risk_count = sum(1 for tx in transactions if tx.risk_level in ["HIGH", "CRITICAL"])

    return {
        "total": len(transactions),
        "blocked_count": blocked_count,
        "high_risk_count": high_risk_count,
        "transactions": [
            {
                "id": tx.id,
                "sender": tx.sender,
                "receiver": tx.receiver,
                "amount": tx.amount,
                "status": tx.status,
                "risk_score": tx.risk_score,
                "risk_level": tx.risk_level,
                "blocked": tx.blocked,
                "created_at": tx.created_at,
            }
            for tx in transactions
        ],
    }
