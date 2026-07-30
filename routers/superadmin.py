"""API Super Admin (stats, chaîne d'audit, métriques modèle, contestations)."""

import json
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from sqlalchemy import func, select

from config import SettingsDep
from database import DbSession
from database.models import BlockchainAuditBlock, Dispute, FraudAlert, Transaction, User
from routers.disputes import dispute_to_dict
from routers.transactions import parse_reasons
from schemas import DisputeDecisionRequest
from services.audit import append_audit_block
from services.auth import CurrentSuperAdmin
from services.email import send_email

router = APIRouter(prefix="/superadmin/api", tags=["Super Admin"])
METRICS_PATH = Path(__file__).resolve().parent.parent / "models" / "model_metrics.json"


def _chain_valid(blocks: list[BlockchainAuditBlock]) -> tuple[bool, int | None]:
    prev_hash = "0" * 64
    for i, blk in enumerate(blocks):
        if blk.block_index != i or blk.previous_hash != prev_hash:
            return False, i
        prev_hash = blk.block_hash
    return True, None


@router.get("/stats")
async def stats(db: DbSession, admin: CurrentSuperAdmin):
    total_users = (await db.execute(select(func.count()).select_from(User))).scalar_one()
    total_tx = (await db.execute(select(func.count()).select_from(Transaction))).scalar_one()
    total_blocked = (
        await db.execute(
            select(func.count()).select_from(Transaction).where(Transaction.blocked.is_(True))
        )
    ).scalar_one()
    total_alerts = (await db.execute(select(func.count()).select_from(FraudAlert))).scalar_one()
    total_blocks = (
        await db.execute(select(func.count()).select_from(BlockchainAuditBlock))
    ).scalar_one()
    blocks = (
        (
            await db.execute(
                select(BlockchainAuditBlock).order_by(BlockchainAuditBlock.block_index.asc())
            )
        )
        .scalars()
        .all()
    )
    valid, _ = _chain_valid(blocks)
    return {
        "total_users": total_users,
        "total_transactions": total_tx,
        "total_blocked": total_blocked,
        "total_alerts": total_alerts,
        "total_audit_blocks": total_blocks,
        "chain_valid": valid,
    }


@router.get("/transactions")
async def list_transactions(db: DbSession, admin: CurrentSuperAdmin, limit: int = 30):
    rows = (
        (await db.execute(select(Transaction).order_by(Transaction.created_at.desc()).limit(limit)))
        .scalars()
        .all()
    )
    return {
        "transactions": [
            {
                "tx_ref": tx.id,
                "sender": tx.sender,
                "receiver": tx.receiver,
                "amount": tx.amount,
                "risk_score": tx.risk_score,
                "risk_level": tx.risk_level,
                "blocked": tx.blocked,
                "approved": tx.approved,
                "reasons": parse_reasons(tx.block_reasons),
                "status": tx.status,
                "created_at": tx.created_at.isoformat() if tx.created_at else None,
            }
            for tx in rows
        ]
    }


@router.post("/transactions/{tx_ref}/approve")
async def approve_transaction(tx_ref: str, db: DbSession, admin: CurrentSuperAdmin):
    tx = await db.get(Transaction, tx_ref)
    if not tx:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction introuvable")
    tx.blocked = False
    tx.status = "approved"
    tx.approved = True
    # Lève aussi l'alerte fraude associée (justificatifs vérifiés)
    alerts = (
        (await db.execute(select(FraudAlert).where(FraudAlert.transaction_id == tx_ref)))
        .scalars()
        .all()
    )
    for alert in alerts:
        alert.blocked = False

    # Levée de blocage tracée dans la chaîne d'audit immuable
    await append_audit_block(
        db,
        "APPROVAL_GRANTED",
        {
            "tx_ref": tx_ref,
            "sender": tx.sender,
            "amount": tx.amount,
            "approved_by": admin.email,
        },
    )
    await db.commit()
    return {"ok": True, "tx_ref": tx_ref}


@router.get("/alerts")
async def list_alerts(db: DbSession, admin: CurrentSuperAdmin, limit: int = 20):
    rows = (
        (await db.execute(select(FraudAlert).order_by(FraudAlert.created_at.desc()).limit(limit)))
        .scalars()
        .all()
    )
    return {
        "alerts": [
            {
                "id": a.id,
                "transaction_id": a.transaction_id,
                "suspect": a.suspect_address,
                "victim": a.victim_address,
                "amount": a.amount,
                "risk_score": a.risk_score,
                "risk_level": a.risk_level,
                "model_used": a.model_used,
                "reasons": a.block_reason.split("; ") if a.block_reason else [],
                "features": json.loads(a.features_json) if a.features_json else {},
                "blocked": a.blocked,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in rows
        ]
    }


@router.get("/users")
async def list_users(db: DbSession, admin: CurrentSuperAdmin):
    rows = (await db.execute(select(User).order_by(User.created_at.desc()))).scalars().all()
    return {
        "users": [
            {
                "id": u.id,
                "email": u.email,
                "wallet": u.wallet_address,
                "role": u.role,
                "is_active": u.is_active,
                "created_at": u.created_at.isoformat() if u.created_at else None,
            }
            for u in rows
        ]
    }


@router.get("/disputes")
async def list_disputes(db: DbSession, admin: CurrentSuperAdmin, limit: int = 50):
    """Contestations à instruire (les plus récentes d'abord, pending en tête)."""
    rows = (
        await db.execute(
            select(Dispute, Transaction, User)
            .join(Transaction, Dispute.transaction_id == Transaction.id)
            .join(User, Dispute.user_id == User.id)
            .order_by(Dispute.created_at.desc())
            .limit(limit)
        )
    ).all()
    disputes = []
    for d, tx, u in rows:
        item = dispute_to_dict(d, tx)
        item["user_email"] = u.email
        item["user_wallet"] = u.wallet_address
        disputes.append(item)
    pending = sum(1 for d in disputes if d["status"] == "pending")
    return {"total": len(disputes), "pending": pending, "disputes": disputes}


@router.post("/disputes/{dispute_id}/decide")
async def decide_dispute(
    dispute_id: str,
    request: DisputeDecisionRequest,
    db: DbSession,
    admin: CurrentSuperAdmin,
    settings: SettingsDep,
    background_tasks: BackgroundTasks,
):
    """Accepte ou refuse une contestation, notifie l'utilisateur par email.

    Accepter = lever le blocage de la transaction (même effet que le bouton
    « Autoriser »), tracé dans la chaîne d'audit. Refuser = la transaction
    reste bloquée, avec la justification de l'admin.
    """
    dispute = await db.get(Dispute, dispute_id)
    if not dispute:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contestation introuvable")
    if dispute.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Contestation déjà instruite"
        )

    tx = await db.get(Transaction, dispute.transaction_id)
    user = await db.get(User, dispute.user_id)

    dispute.status = "accepted" if request.accept else "rejected"
    dispute.admin_response = request.response
    dispute.resolved_at = datetime.utcnow()

    if request.accept and tx:
        tx.blocked = False
        tx.status = "approved"
        tx.approved = True
        alerts = (
            (await db.execute(select(FraudAlert).where(FraudAlert.transaction_id == tx.id)))
            .scalars()
            .all()
        )
        for alert in alerts:
            alert.blocked = False

    await append_audit_block(
        db,
        "DISPUTE_ACCEPTED" if request.accept else "DISPUTE_REJECTED",
        {
            "dispute_id": dispute.id,
            "tx_ref": dispute.transaction_id,
            "amount": tx.amount if tx else None,
            "decided_by": admin.email,
        },
    )
    await db.commit()

    # Notifier l'utilisateur de la décision
    if user:
        verdict = "acceptée — votre transaction est débloquée" if request.accept else "refusée"
        couleur = "#30B96E" if request.accept else "#CC0000"
        background_tasks.add_task(
            send_email,
            settings,
            user.email,
            f"Votre contestation a été {'acceptée ✓' if request.accept else 'refusée ✕'} — GTA-IT Fintech",
            f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 1.5rem;">
              <h2 style="color:{couleur};">Votre contestation a été {verdict}</h2>
              <p>Transaction <code>{dispute.transaction_id[:8]}…</code>
                 ({tx.amount:.2f} FTK) : la décision du contrôle de conformité est
                 <b style="color:{couleur};">{"ACCEPTÉE" if request.accept else "REFUSÉE"}</b>.</p>
              {f'<p style="background:#F5F7FA; padding:1rem; border-radius:8px;">Justification : « {request.response} »</p>' if request.response else ""}
              <p><a href="{settings.app_base_url.rstrip('/')}/dashboard">Voir mes transactions</a></p>
            </div>
            """,
        )

    return {"ok": True, "dispute_id": dispute.id, "status": dispute.status}


@router.get("/model/metrics")
async def model_metrics(admin: CurrentSuperAdmin):
    if not METRICS_PATH.exists():
        raise HTTPException(status_code=404, detail="Métriques modèle introuvables")
    return json.loads(METRICS_PATH.read_text(encoding="utf-8"))


@router.get("/chain")
async def chain(db: DbSession, admin: CurrentSuperAdmin, limit: int = 15):
    rows = (
        (
            await db.execute(
                select(BlockchainAuditBlock)
                .order_by(BlockchainAuditBlock.block_index.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    total = (await db.execute(select(func.count()).select_from(BlockchainAuditBlock))).scalar_one()
    return {
        "total": total,
        "blocks": [
            {
                "block_index": b.block_index,
                "event_type": b.event_type,
                "data": json.loads(b.data) if b.data else {},
                "previous_hash": b.previous_hash,
                "block_hash": b.block_hash,
                "timestamp": b.created_at.isoformat() if b.created_at else None,
            }
            for b in rows
        ],
    }


@router.get("/chain/verify")
async def chain_verify(db: DbSession, admin: CurrentSuperAdmin):
    blocks = (
        (
            await db.execute(
                select(BlockchainAuditBlock).order_by(BlockchainAuditBlock.block_index.asc())
            )
        )
        .scalars()
        .all()
    )
    valid, broken_at = _chain_valid(blocks)
    if not valid:
        return {"valid": False, "broken_at": broken_at}
    return {"valid": True, "blocks": len(blocks)}
