"""Contestations de transactions refusées (côté utilisateur).

Une transaction bloquée par l'IA peut être contestée par son auteur, avec
un message explicatif. Le super admin instruit la demande dans sa console
(/superadmin/api/disputes) ; l'utilisateur suit l'état ici :
pending → accepted (blocage levé) ou rejected.
"""

import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from sqlalchemy import select

from config import SettingsDep
from database import DbSession
from database.models import Dispute, Transaction
from routers.transactions import parse_reasons
from schemas import DisputeCreateRequest
from services.auth import CurrentUser
from services.email import send_email

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/disputes", tags=["Disputes"])

STATUS_LABELS = {"pending": "En attente", "accepted": "Acceptée", "rejected": "Refusée"}


def dispute_to_dict(d: Dispute, tx: Transaction | None = None) -> dict:
    return {
        "id": d.id,
        "transaction_id": d.transaction_id,
        "message": d.message,
        "status": d.status,
        "status_label": STATUS_LABELS.get(d.status, d.status),
        "admin_response": d.admin_response,
        "created_at": d.created_at.isoformat() if d.created_at else None,
        "resolved_at": d.resolved_at.isoformat() if d.resolved_at else None,
        "transaction": {
            "amount": tx.amount,
            "receiver": tx.receiver,
            "risk_score": tx.risk_score,
            "risk_level": tx.risk_level,
            "blocked": tx.blocked,
            "reasons": parse_reasons(tx.block_reasons),
        }
        if tx
        else None,
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_dispute(
    request: DisputeCreateRequest,
    db: DbSession,
    user: CurrentUser,
    settings: SettingsDep,
    background_tasks: BackgroundTasks,
):
    """Conteste une transaction refusée (une contestation ouverte par transaction)."""
    tx = await db.get(Transaction, request.transaction_id)
    if not tx or tx.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Transaction introuvable"
        )
    if not tx.blocked:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cette transaction n'est pas bloquée — rien à contester",
        )

    existing = (
        (
            await db.execute(
                select(Dispute).where(
                    Dispute.transaction_id == tx.id, Dispute.status == "pending"
                )
            )
        )
        .scalars()
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Une contestation est déjà en cours pour cette transaction",
        )

    dispute = Dispute(
        id=str(uuid.uuid4()),
        transaction_id=tx.id,
        user_id=user.id,
        message=request.message,
    )
    db.add(dispute)
    await db.commit()

    # Prévenir le super admin qu'une contestation attend sa décision
    background_tasks.add_task(
        send_email,
        settings,
        settings.superadmin_email,
        f"📩 Contestation reçue — {tx.amount:.2f} FTK bloqués",
        f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 1.5rem;">
          <h2 style="color:#1A202C;">📩 Nouvelle contestation</h2>
          <p><b>{user.email}</b> conteste le blocage de la transaction
             <code>{tx.id[:8]}…</code> ({tx.amount:.2f} FTK, score {tx.risk_score}/100).</p>
          <p style="background:#F5F7FA; padding:1rem; border-radius:8px;">« {request.message} »</p>
          <p><a href="{settings.app_base_url.rstrip('/')}/superadmin">Instruire dans la console super admin</a></p>
        </div>
        """,
    )

    logger.info("Contestation %s créée par %s pour tx %s", dispute.id, user.email, tx.id)
    return dispute_to_dict(dispute, tx)


@router.get("/mine")
async def my_disputes(db: DbSession, user: CurrentUser, limit: int = 50):
    """Contestations de l'utilisateur, avec l'état d'instruction."""
    rows = (
        (
            await db.execute(
                select(Dispute, Transaction)
                .join(Transaction, Dispute.transaction_id == Transaction.id)
                .where(Dispute.user_id == user.id)
                .order_by(Dispute.created_at.desc())
                .limit(limit)
            )
        )
        .all()
    )
    return {"total": len(rows), "disputes": [dispute_to_dict(d, tx) for d, tx in rows]}
