"""Chaîne d'audit immuable (hash chain applicative).

Chaque événement sensible (fraude détectée, blocage levé) est scellé dans
un bloc chaîné cryptographiquement : block_hash = SHA-256(index | hash
précédent | type | données | horodatage). Toute altération a posteriori
d'un bloc casse la chaîne — c'est ce que vérifie /superadmin/api/chain/verify.
"""

import hashlib
import json
import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import BlockchainAuditBlock

logger = logging.getLogger(__name__)

_GENESIS_PREV = "0" * 64


def _block_hash(index: int, prev_hash: str, event_type: str, data: str, ts: str) -> str:
    payload = f"{index}|{prev_hash}|{event_type}|{data}|{ts}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _build_block(index: int, prev_hash: str, event_type: str, data: dict) -> BlockchainAuditBlock:
    now = datetime.utcnow()
    data_json = json.dumps(data, ensure_ascii=False, sort_keys=True, default=str)
    return BlockchainAuditBlock(
        block_index=index,
        event_type=event_type,
        data=data_json,
        previous_hash=prev_hash,
        block_hash=_block_hash(index, prev_hash, event_type, data_json, now.isoformat()),
        created_at=now,
    )


async def append_audit_block(
    db: AsyncSession, event_type: str, data: dict
) -> BlockchainAuditBlock:
    """Ajoute un bloc à la chaîne (crée le bloc GENESIS au premier appel).

    Le bloc est ajouté à la session : c'est l'appelant qui commit, pour que
    l'événement métier et son bloc d'audit partagent la même transaction.
    """
    last = (
        (
            await db.execute(
                select(BlockchainAuditBlock)
                .order_by(BlockchainAuditBlock.block_index.desc())
                .limit(1)
            )
        )
        .scalars()
        .first()
    )

    if last is None:
        genesis = _build_block(
            0, _GENESIS_PREV, "GENESIS", {"message": "Ouverture de la chaîne d'audit GTA Fintech"}
        )
        db.add(genesis)
        last = genesis

    block = _build_block(last.block_index + 1, last.block_hash, event_type, data)
    db.add(block)
    logger.info("Bloc d'audit #%s ajouté : %s", block.block_index, event_type)
    return block
