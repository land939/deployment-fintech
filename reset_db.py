"""Vide et recrée les tables (async).

Usage:
  python reset_db.py --force
"""

import asyncio
import sys

from config import get_settings
from database import Base, init_db


async def reset_database() -> None:
    settings = get_settings()
    engine, _ = await init_db(settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    print("Base de données vidée et tables recréées.")


if __name__ == "__main__":
    if "--force" not in sys.argv:
        reponse = input("Supprimer toutes les données ? (oui/non) : ")
        if reponse.strip().lower() not in ("oui", "o", "yes", "y"):
            print("Annulé.")
            sys.exit(0)
    asyncio.run(reset_database())
