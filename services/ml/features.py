"""Construction des features de fraude à partir de l'historique wallet.

Mêmes définitions que train_fraud_model.py — toute divergence fausserait
la prédiction en production.
"""

from datetime import datetime, timedelta

from sqlalchemy import Selectable, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from database.models import Transaction, User

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


async def _scalar(db: AsyncSession, stmt: Selectable) -> float | int | None:
    return (await db.execute(stmt)).scalar_one()


def _sender_eq(sender: str) -> ColumnElement:
    return func.lower(Transaction.sender) == sender


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
    sender_match = _sender_eq(sender)

    prev_1h = await _scalar(
        db,
        select(func.count())
        .select_from(Transaction)
        .where(sender_match, Transaction.created_at >= now - timedelta(hours=1)),
    )
    prev_24h = await _scalar(
        db,
        select(func.count())
        .select_from(Transaction)
        .where(sender_match, Transaction.created_at >= now - timedelta(hours=24)),
    )
    n_legit = await _scalar(
        db,
        select(func.count())
        .select_from(Transaction)
        .where(sender_match, Transaction.blocked.is_(False)),
    )
    avg_amt = await _scalar(
        db,
        select(func.avg(Transaction.amount)).where(sender_match, Transaction.blocked.is_(False)),
    )
    last_tx = (
        (
            await db.execute(
                select(Transaction)
                .where(sender_match)
                .order_by(Transaction.created_at.desc())
                .limit(1)
            )
        )
        .scalars()
        .first()
    )
    frauds = await _scalar(
        db,
        select(func.count())
        .select_from(Transaction)
        .where(sender_match, Transaction.blocked.is_(True)),
    )
    known = await _scalar(
        db,
        select(func.count())
        .select_from(Transaction)
        .where(sender_match, func.lower(Transaction.receiver) == receiver_l),
    )
    recv_24h = (
        await _scalar(
            db,
            select(func.count(func.distinct(func.lower(Transaction.receiver)))).where(
                sender_match, Transaction.created_at >= now - timedelta(hours=24)
            ),
        )
        or 0
    )

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
        "tx_count_1h": float(prev_1h or 0),
        "tx_count_24h": float(prev_24h or 0),
        "amount_avg_ratio": float(amount / avg_amt) if n_legit and avg_amt else 1.0,
        "seconds_since_last_tx": float(since_last),
        "is_new_receiver": 0.0 if known else 1.0,
        "unique_receivers_24h": float(recv_24h),
        "past_fraud_count": float(frauds or 0),
    }
