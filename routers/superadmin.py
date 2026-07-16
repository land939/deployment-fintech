"""API Super Admin (stats, chaîne d'audit, métriques modèle)."""

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from database import DbSession
from database.models import BlockchainAuditBlock, FraudAlert, Transaction, User

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
async def stats(db: DbSession):
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
async def list_transactions(db: DbSession, limit: int = 30):
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
                "status": tx.status,
                "created_at": tx.created_at.isoformat() if tx.created_at else None,
            }
            for tx in rows
        ]
    }


@router.post("/transactions/{tx_ref}/approve")
async def approve_transaction(tx_ref: str, db: DbSession):
    tx = await db.get(Transaction, tx_ref)
    if not tx:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction introuvable")
    tx.blocked = False
    tx.status = "approved"
    tx.approved = True
    await db.commit()
    return {"ok": True, "tx_ref": tx_ref}


@router.get("/alerts")
async def list_alerts(db: DbSession, limit: int = 20):
    rows = (
        (await db.execute(select(FraudAlert).order_by(FraudAlert.created_at.desc()).limit(limit)))
        .scalars()
        .all()
    )
    return {
        "alerts": [
            {
                "id": a.id,
                "suspect": a.suspect_address,
                "amount": a.amount,
                "risk_score": a.risk_score,
                "risk_level": a.risk_level,
                "blocked": a.blocked,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in rows
        ]
    }


@router.get("/users")
async def list_users(db: DbSession):
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


@router.get("/model/metrics")
async def model_metrics():
    if not METRICS_PATH.exists():
        raise HTTPException(status_code=404, detail="Métriques modèle introuvables")
    return json.loads(METRICS_PATH.read_text(encoding="utf-8"))


@router.get("/chain")
async def chain(db: DbSession, limit: int = 15):
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
async def chain_verify(db: DbSession):
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
