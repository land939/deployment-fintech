"""Construction des features de fraude à partir de l'historique wallet.

Mêmes définitions que train_fraud_model.py — toute divergence fausserait
la prédiction en production.
"""

from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Transaction, User

# Plafond du délai depuis la dernière tx (aligné sur train_fraud_model.py)
CAP_SILENCE_S = 7 * 86400

FEATURE_COLS = [
    "amount",
    "hour",
    "day_of_week",
    "account_age_days",
    "tx_count_1h",
    "tx_count_24h",
    "amount_avg_ratio",
    "seconds_since_last_tx",
    "is_new_receiver",
    "unique_receivers_24h",
    "past_fraud_count",
]


async def build_fraud_features(
    db: AsyncSession,
    user: User | None,
    amount: float,
    receiver: str,
    hour: int | None = None,
) -> dict[str, float]:
    """Construit le vecteur de features à partir de users + transactions."""
    now = datetime.utcnow()
    sender = (user.wallet_address if user else "").lower()
    receiver_l = receiver.lower()

    base = select(Transaction).where(func.lower(Transaction.sender) == sender)

    prev_1h = (
        await db.execute(
            select(func.count())
            .select_from(Transaction)
            .where(
                func.lower(Transaction.sender) == sender,
                Transaction.created_at >= now - timedelta(hours=1),
            )
        )
    ).scalar_one()

    prev_24h = (
        await db.execute(
            select(func.count())
            .select_from(Transaction)
            .where(
                func.lower(Transaction.sender) == sender,
                Transaction.created_at >= now - timedelta(hours=24),
            )
        )
    ).scalar_one()

    # Moyenne sur transactions légitimes uniquement (blocked=False)
    n_legit = (
        await db.execute(
            select(func.count())
            .select_from(Transaction)
            .where(
                func.lower(Transaction.sender) == sender,
                Transaction.blocked.is_(False),
            )
        )
    ).scalar_one()

    avg_amt = (
        await db.execute(
            select(func.avg(Transaction.amount)).where(
                func.lower(Transaction.sender) == sender,
                Transaction.blocked.is_(False),
            )
        )
    ).scalar_one()

    last_tx = (
        (await db.execute(base.order_by(Transaction.created_at.desc()).limit(1))).scalars().first()
    )

    frauds = (
        await db.execute(
            select(func.count())
            .select_from(Transaction)
            .where(
                func.lower(Transaction.sender) == sender,
                Transaction.blocked.is_(True),
            )
        )
    ).scalar_one()

    known = (
        await db.execute(
            select(func.count())
            .select_from(Transaction)
            .where(
                func.lower(Transaction.sender) == sender,
                func.lower(Transaction.receiver) == receiver_l,
            )
        )
    ).scalar_one()

    recv_24h = (
        await db.execute(
            select(func.count(func.distinct(func.lower(Transaction.receiver)))).where(
                func.lower(Transaction.sender) == sender,
                Transaction.created_at >= now - timedelta(hours=24),
            )
        )
    ).scalar_one() or 0

    account_age = (
        (now - user.created_at).total_seconds() / 86400 if user and user.created_at else 0.0
    )
    since_last = (
        min((now - last_tx.created_at).total_seconds(), CAP_SILENCE_S)
        if last_tx and last_tx.created_at
        else CAP_SILENCE_S
    )

    return {
        "amount": float(amount),
        "hour": float(hour if hour is not None else datetime.now().hour),
        "day_of_week": float(now.weekday()),
        "account_age_days": float(max(0.0, account_age)),
        "tx_count_1h": float(prev_1h),
        "tx_count_24h": float(prev_24h),
        "amount_avg_ratio": float(amount / avg_amt) if n_legit and avg_amt else 1.0,
        "seconds_since_last_tx": float(since_last),
        "is_new_receiver": 0.0 if known else 1.0,
        "unique_receivers_24h": float(recv_24h),
        "past_fraud_count": float(frauds),
    }
