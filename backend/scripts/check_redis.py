import asyncio

from rate_limit import redis_healthcheck
from settings import get_settings


async def main() -> None:
    settings = get_settings()
    if not await redis_healthcheck():
        raise SystemExit(f"Brak odpowiedzi Redis pod {settings.redis_url}")
    print(f"Redis odpowiada pod {settings.redis_url}")


if __name__ == "__main__":
    asyncio.run(main())
