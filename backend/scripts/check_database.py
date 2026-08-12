import asyncio

from db.session import get_engine
from sqlalchemy import text


async def check_database() -> None:
    engine = get_engine()
    try:
        async with engine.connect() as connection:
            result = await connection.execute(
                text("SELECT current_database(), current_user, version()")
            )
            database, user, version = result.one()
            print(f"Połączenie działa: database={database}, user={user}")
            print(version)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(check_database())
