"""Routes transactions."""

import json
import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from sqlalchemy import func, or_, select

from config import SettingsDep
from database import DbSession
from database.models import FraudAlert, Transaction
from schemas import TransactionRequest, TransactionResponse, TxConfirmRequest
from services.audit import append_audit_block
from services.auth import CurrentSuperAdmin, CurrentUser
from services.blockchain import get_blockchain_service
from services.email import build_fraud_alert_email_html, send_email
from services.ml import get_fraud_service
from services.ml.features import build_fraud_features
from services.rates import ftk_to_eth
from utils import is_valid_wallet

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/transactions", tags=["Transactions"])


def parse_reasons(raw: str | None) -> list[str]:
    """Décode la colonne JSON block_reasons (liste vide si absente/corrompue)."""
    if not raw:
        return []
    try:
        value = json.loads(raw)
        return value if isinstance(value, list) else []
    except (ValueError, TypeError):
        return []


@router.post("/send", response_model=TransactionResponse)
async def send_transaction(
    request: TransactionRequest,
    db: DbSession,
    settings: SettingsDep,
    user: CurrentUser,
    background_tasks: BackgroundTasks,
):
    """Envoie une transaction avec détection de fraude, au nom de l'utilisateur authentifié."""
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

    ml_service = get_fraud_service()
    if ml_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Modèles ML indisponibles",
        )

    if request.features:
        fraud_features = request.features
    else:
        fraud_features = await build_fraud_features(db, user, request.amount, request.receiver)
    fraud_result = ml_service.predict_fraud(fraud_features)
    reasons = fraud_result.get("reasons", [])
    is_blocked = fraud_result.get("blocked", False)

    tx_id = str(uuid.uuid4())
    transaction = Transaction(
        id=tx_id,
        user_id=user.id,
        sender=user.wallet_address,
        receiver=request.receiver,
        amount=request.amount,
        risk_score=fraud_result.get("risk_score", 0),
        risk_level=fraud_result.get("risk_level", "UNKNOWN"),
        blocked=is_blocked,
        block_reasons=json.dumps(reasons, ensure_ascii=False) if reasons else None,
        status="pending" if not is_blocked else "blocked",
    )
    db.add(transaction)

    if is_blocked:
        # Alerte fraude détaillée : features + raisons, consultées par le
        # super admin avant d'autoriser la transaction.
        db.add(
            FraudAlert(
                id=str(uuid.uuid4()),
                user_id=user.id,
                transaction_id=tx_id,
                suspect_address=user.wallet_address,
                victim_address=request.receiver,
                amount=request.amount,
                risk_score=fraud_result.get("risk_score", 0),
                risk_level=fraud_result.get("risk_level", "UNKNOWN"),
                model_used="XGBoost_v2",
                features_json=json.dumps(fraud_features, ensure_ascii=False),
                block_reason="; ".join(reasons) if reasons else None,
                blocked=True,
            )
        )

        # Bloc d'audit immuable, scellé dans la même transaction SQL
        await append_audit_block(
            db,
            "FRAUD_DETECTED",
            {
                "tx_ref": tx_id,
                "sender": user.wallet_address,
                "receiver": request.receiver,
                "amount": request.amount,
                "risk_score": fraud_result.get("risk_score", 0),
                "risk_level": fraud_result.get("risk_level", "UNKNOWN"),
            },
        )

        # Email d'alerte au super admin — après la réponse HTTP (SMTP lent)
        background_tasks.add_task(
            send_email,
            settings,
            settings.superadmin_email,
            f"🚨 Fraude bloquée — {request.amount:.2f} FTK "
            f"(score {fraud_result.get('risk_score', 0)}/100)",
            build_fraud_alert_email_html(
                tx_id,
                user.wallet_address,
                request.receiver,
                request.amount,
                fraud_result.get("risk_score", 0),
                fraud_result.get("risk_level", "UNKNOWN"),
                reasons,
            ),
        )

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
        blocked=is_blocked,
        reasons=reasons,
        amount_eth=ftk_to_eth(request.amount, settings),
        created_at=transaction.created_at or datetime.utcnow(),
    )


@router.post("/{tx_id}/confirm")
async def confirm_transaction(
    tx_id: str,
    request: TxConfirmRequest,
    db: DbSession,
    user: CurrentUser,
):
    """Enregistre le hash on-chain d'une transaction signée via MetaMask.

    Appelé par le front après que l'utilisateur a signé le transfert ERC-20
    dans MetaMask. Si Ganache est joignable, le reçu est vérifié
    (status == 1) avant de marquer la transaction « confirmed ».
    """
    tx = await db.get(Transaction, tx_id)
    if not tx or tx.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Transaction introuvable"
        )
    if tx.blocked:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Transaction bloquée par l'IA — transfert on-chain interdit",
        )

    chain = get_blockchain_service()
    verified = False
    if chain and chain.connected:
        receipt = chain.get_transaction_receipt(request.tx_hash)
        if receipt is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Hash introuvable sur la chaîne — transaction non minée ?",
            )
        if receipt["status"] != 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La transaction on-chain a été rejetée (revert)",
            )
        verified = True

    tx.hash = request.tx_hash
    tx.tx_hash_ref = request.tx_hash
    tx.status = "confirmed"
    await db.commit()
    logger.info("Transaction %s confirmée on-chain (%s, vérifiée=%s)", tx_id, request.tx_hash, verified)
    return {"ok": True, "tx_ref": tx_id, "tx_hash": request.tx_hash, "verified": verified}


@router.get("/recent")
async def get_recent_transactions(db: DbSession, user: CurrentUser, limit: int = 20):
    """Transactions récentes de l'utilisateur authentifié (envoyées ou reçues).

    Vue globale : /superadmin/api/transactions (réservée au super admin).
    """
    wallet = user.wallet_address.lower()
    result = await db.execute(
        select(Transaction)
        .where(
            or_(
                func.lower(Transaction.sender) == wallet,
                func.lower(Transaction.receiver) == wallet,
            )
        )
        .order_by(Transaction.created_at.desc())
        .limit(limit)
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
                "risk_score": tx.risk_score,
                "risk_level": tx.risk_level,
                "blocked": tx.blocked,
                "approved": tx.approved,
                "reasons": parse_reasons(tx.block_reasons),
                "created_at": tx.created_at,
            }
            for tx in transactions
        ],
    }


@router.get("/all")
async def get_all_transactions(
    db: DbSession, admin: CurrentSuperAdmin, skip: int = 0, limit: int = 100
):
    """Toutes les transactions, toutes plateformes confondues (super admin uniquement)."""
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
                "approved": tx.approved,
                "reasons": parse_reasons(tx.block_reasons),
                "created_at": tx.created_at,
            }
            for tx in transactions
        ],
    }
