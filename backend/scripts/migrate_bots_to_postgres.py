import argparse
import asyncio
import uuid
from datetime import datetime
from pathlib import Path

from chess_logic.bots import BotStore
from db.models import Bot, BotVisibility
from db.session import get_session_factory
from sqlalchemy import select

DEFAULT_SQLITE_PATH = Path(__file__).resolve().parents[1] / "data" / "bots.sqlite3"


def parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value)


async def migrate(source: Path) -> tuple[int, int]:
    legacy_bots = BotStore(str(source)).list()
    imported = 0
    skipped = 0

    async with get_session_factory()() as db:
        for profile in legacy_bots:
            bot_id = uuid.UUID(profile["id"])
            if await db.scalar(select(Bot.id).where(Bot.id == bot_id)) is not None:
                skipped += 1
                continue
            clean = BotStore.validate(profile)
            db.add(
                Bot(
                    id=bot_id,
                    owner_id=None,
                    visibility=BotVisibility.PUBLIC,
                    created_at=parse_datetime(profile["created_at"]),
                    updated_at=parse_datetime(profile["updated_at"]),
                    **clean,
                )
            )
            imported += 1
        await db.commit()
    return imported, skipped


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Idempotentnie przenosi boty SQLite do PostgreSQL jako publiczne."
    )
    parser.add_argument("--source", type=Path, default=DEFAULT_SQLITE_PATH)
    args = parser.parse_args()
    imported, skipped = await migrate(args.source)
    print(f"Zaimportowano: {imported}; pominięto istniejące: {skipped}")


if __name__ == "__main__":
    asyncio.run(main())
