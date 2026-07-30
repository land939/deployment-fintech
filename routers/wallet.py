"""Wallet FTK : solde on-chain (ERC-20), conversion ETH, historique, MetaMask.

Le solde vient du smart contract FintechToken (balanceOf) via Ganache.
Si la blockchain est hors ligne, les endpoints répondent avec
on_chain=False plutôt que d'échouer — l'UI dégrade proprement.
"""

import logging

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, or_, select

from config import SettingsDep
from database import DbSession
from database.models import Transaction, User
from schemas import WalletLinkRequest
from services.auth import CurrentUser
from services.blockchain import get_blockchain_service
from services.rates import ftk_to_eth, get_ftk_eth_rate
from utils import is_valid_wallet

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/wallet", tags=["Wallet"])


@router.get("/summary")
async def wallet_summary(db: DbSession, user: CurrentUser, settings: SettingsDep):
    """Solde FTK du wallet de l'utilisateur + équivalent ETH + volumes."""
    chain = get_blockchain_service()
    balance = chain.get_balance(user.wallet_address) if chain and chain.connected else None
    rate = get_ftk_eth_rate(settings)

    wallet = user.wallet_address.lower()
    credits = (
        await db.execute(
            select(func.coalesce(func.sum(Transaction.amount), 0.0)).where(
                func.lower(Transaction.receiver) == wallet,
                Transaction.blocked.is_(False),
            )
        )
    ).scalar_one()
    debits = (
        await db.execute(
            select(func.coalesce(func.sum(Transaction.amount), 0.0)).where(
                func.lower(Transaction.sender) == wallet,
                Transaction.blocked.is_(False),
            )
        )
    ).scalar_one()

    return {
        "wallet": user.wallet_address,
        "on_chain": balance is not None,
        "balance_ftk": round(balance, 4) if balance is not None else None,
        "balance_eth": ftk_to_eth(balance, settings) if balance is not None else None,
        "ftk_eth_rate": rate,
        "total_credits_ftk": round(float(credits), 2),
        "total_debits_ftk": round(float(debits), 2),
    }


@router.get("/history")
async def wallet_history(db: DbSession, user: CurrentUser, settings: SettingsDep, limit: int = 30):
    """Historique des crédits (reçus) et débits (envoyés) du wallet."""
    wallet = user.wallet_address.lower()
    rows = (
        (
            await db.execute(
                select(Transaction)
                .where(
                    or_(
                        func.lower(Transaction.sender) == wallet,
                        func.lower(Transaction.receiver) == wallet,
                    ),
                    Transaction.blocked.is_(False),
                )
                .order_by(Transaction.created_at.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return {
        "total": len(rows),
        "movements": [
            {
                "id": tx.id,
                "direction": "debit" if tx.sender.lower() == wallet else "credit",
                "amount_ftk": tx.amount,
                "amount_eth": ftk_to_eth(tx.amount, settings),
                "counterparty": tx.receiver if tx.sender.lower() == wallet else tx.sender,
                "status": tx.status,
                "tx_hash": tx.hash,
                "created_at": tx.created_at.isoformat() if tx.created_at else None,
            }
            for tx in rows
        ],
    }


@router.get("/balance/{address}")
async def wallet_balance(address: str, user: CurrentUser, settings: SettingsDep):
    """Solde on-chain d'une adresse quelconque (lecture publique du contrat)."""
    if not is_valid_wallet(address):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Adresse wallet invalide"
        )
    chain = get_blockchain_service()
    if not chain or not chain.connected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Blockchain hors ligne — solde indisponible",
        )
    balance = chain.get_balance(address)
    if balance is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="Lecture du contrat impossible"
        )
    return {
        "address": address,
        "balance": round(balance, 4),
        "balance_eth": ftk_to_eth(balance, settings),
    }


@router.post("/link")
async def link_wallet(request: WalletLinkRequest, db: DbSession, user: CurrentUser):
    """Associe l'adresse MetaMask connectée au compte de l'utilisateur."""
    new_addr = request.address
    if new_addr.lower() == user.wallet_address.lower():
        return {"ok": True, "wallet": user.wallet_address, "changed": False}

    taken = (
        (
            await db.execute(
                select(User).where(
                    func.lower(User.wallet_address) == new_addr.lower(), User.id != user.id
                )
            )
        )
        .scalars()
        .first()
    )
    if taken:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cette adresse est déjà associée à un autre compte",
        )

    old = user.wallet_address
    user.wallet_address = new_addr
    await db.commit()
    logger.info("Wallet de %s mis à jour : %s → %s", user.email, old, new_addr)
    return {"ok": True, "wallet": new_addr, "changed": True}
