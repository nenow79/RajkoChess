import asyncio

from fastapi import HTTPException

from rate_limit import concurrency_slot, consume_rate_limit, get_redis, private_key


async def main() -> None:
    identity = "diagnostic-local-user"
    rate_key = f"rajko:rate:diagnostic:{private_key(identity)}"
    lock_key = f"rajko:lock:diagnostic:{private_key(identity)}"
    redis = get_redis()
    await redis.delete(rate_key, lock_key)
    try:
        first, _ = await consume_rate_limit(
            bucket="diagnostic", identity=identity, limit=2, window_seconds=30
        )
        second, _ = await consume_rate_limit(
            bucket="diagnostic", identity=identity, limit=2, window_seconds=30
        )
        if (first, second) != (1, 2):
            raise SystemExit("Licznik Redis nie jest atomowy")
        try:
            await consume_rate_limit(
                bucket="diagnostic", identity=identity, limit=2, window_seconds=30
            )
        except HTTPException as exc:
            if exc.status_code != 429 or "Retry-After" not in (exc.headers or {}):
                raise
        else:
            raise SystemExit("Redis nie zatrzymał żądania ponad limitem")

        async with concurrency_slot(
            bucket="diagnostic", identity=identity, ttl_seconds=30
        ):
            try:
                async with concurrency_slot(
                    bucket="diagnostic", identity=identity, ttl_seconds=30
                ):
                    pass
            except HTTPException as exc:
                if exc.status_code != 429:
                    raise
            else:
                raise SystemExit("Redis dopuścił dwie równoległe operacje")
    finally:
        await redis.delete(rate_key, lock_key)
        await redis.aclose()
    print("Rate limiter i blokada współbieżności Redis działają poprawnie")


if __name__ == "__main__":
    asyncio.run(main())
