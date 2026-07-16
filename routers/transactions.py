"""Routes transactions."""

import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from config import SettingsDep
from database import DbSession
from database.models import Transaction, User
from schemas import TransactionRequest, TransactionResponse
from services.ml import FraudDetectionService
from services.ml.features import build_fraud_features
from utils import is_valid_wallet

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/transactions", tags=["Transactions"])


@router.post("/send", response_model=TransactionResponse)
async def send_transaction(
    request: TransactionRequest,
    db: DbSession,
    settings: SettingsDep,
):
    """Envoie une transaction avec détection de fraude."""
    if not is_valid_wallet(request.receiver):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Adresse wallet destinataire invalide",
        )

    if request.amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le montant doit être positif",
        )

    # ponytail: pas de JWT encore — premier user pour la démo ; brancher auth JWT ensuite
    result = await db.execute(select(User).limit(1))
    user = result.scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utilisateur introuvable",
        )

    ml_service = FraudDetectionService(settings)
    if request.features:
        fraud_features = request.features
    else:
        fraud_features = await build_fraud_features(db, user, request.amount, request.receiver)
    fraud_result = ml_service.predict_fraud(fraud_features)

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
        "Transaction créée: %s | amount=%s | risk=%s",
        tx_id,
        request.amount,
        fraud_result.get("risk_level"),
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
        created_at=transaction.created_at or datetime.utcnow(),
    )


@router.get("/recent")
async def get_recent_transactions(db: DbSession, limit: int = 20):
    """Transactions récentes."""
    result = await db.execute(
        select(Transaction).order_by(Transaction.created_at.desc()).limit(limit)
    )
    transactions = result.scalars().all()

    return {
        "total": len(transactions),
        "transactions": [
            {
                "id": tx.id,
                "tx_ref": tx.id,
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
async def get_all_transactions(db: DbSession, skip: int = 0, limit: int = 100):
    """Toutes les transactions (admin)."""
    result = await db.execute(
        select(Transaction).order_by(Transaction.created_at.desc()).offset(skip).limit(limit)
    )
    transactions = result.scalars().all()

    blocked_count = sum(1 for tx in transactions if tx.blocked)
    high_risk_count = sum(1 for tx in transactions if tx.risk_level in ["HIGH", "CRITICAL"])

    return {
        "total": len(transactions),
        "blocked_count": blocked_count,
        "high_risk_count": high_risk_count,
        "transactions": [
            {
                "id": tx.id,
                "tx_ref": tx.id,
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
