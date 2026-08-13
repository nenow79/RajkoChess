import hashlib
import hmac
import logging
import secrets
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import AsyncIterator

from fastapi import HTTPException, Request, status
from redis.asyncio import Redis
from redis.exceptions import RedisError
from settings import get_settings

logger = logging.getLogger(__name__)

FIXED_WINDOW_SCRIPT = """
local current = redis.call('INCR', KEYS[1])
if current == 1 then
  redis.call('EXPIRE', KEYS[1], ARGV[1])
end
local ttl = redis.call('TTL', KEYS[1])
return {current, ttl}
"""

RELEASE_LOCK_SCRIPT = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
  return redis.call('DEL', KEYS[1])
end
return 0
"""


class RateLimitStoreUnavailable(Exception):
    pass


@lru_cache
def get_redis() -> Redis:
    return Redis.from_url(get_settings().redis_url, decode_responses=True)


def private_key(value: str) -> str:
    secret = get_settings().rate_limit_key_secret.get_secret_value().encode()
    return hmac.new(secret, value.casefold().encode(), hashlib.sha256).hexdigest()


def request_ip(request: Request) -> str:
    direct = request.client.host if request.client else "unknown"
    if direct in {"127.0.0.1", "::1"}:
        forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
        if forwarded:
            return forwarded
    return direct


async def consume_rate_limit(
    *, bucket: str, identity: str, limit: int, window_seconds: int
) -> tuple[int, int]:
    key = f"rajko:rate:{bucket}:{private_key(identity)}"
    try:
        result = await get_redis().eval(
            FIXED_WINDOW_SCRIPT, 1, key, window_seconds
        )
    except RedisError as exc:
        raise RateLimitStoreUnavailable from exc
    count, retry_after = int(result[0]), max(int(result[1]), 1)
    if count > limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Wykonano zbyt wiele prób. Spróbuj ponownie później.",
            headers={"Retry-After": str(retry_after)},
        )
    return count, retry_after


async def clear_rate_limit(*, bucket: str, identity: str) -> None:
    key = f"rajko:rate:{bucket}:{private_key(identity)}"
    try:
        await get_redis().delete(key)
    except RedisError:
        logger.exception("Nie udało się wyzerować licznika Redis %s", bucket)


async def enforce_rate_limit(
    *,
    bucket: str,
    identity: str,
    limit: int,
    window_seconds: int,
    fail_closed: bool = True,
) -> None:
    try:
        await consume_rate_limit(
            bucket=bucket,
            identity=identity,
            limit=limit,
            window_seconds=window_seconds,
        )
    except RateLimitStoreUnavailable:
        logger.exception("Redis jest niedostępny dla limitu %s", bucket)
        if fail_closed:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Ta funkcja jest chwilowo niedostępna. Spróbuj ponownie później.",
            )


@asynccontextmanager
async def concurrency_slot(
    *, bucket: str, identity: str, ttl_seconds: int = 300
) -> AsyncIterator[None]:
    key = f"rajko:lock:{bucket}:{private_key(identity)}"
    token = secrets.token_urlsafe(24)
    try:
        acquired = await get_redis().set(key, token, ex=ttl_seconds, nx=True)
    except RedisError as exc:
        logger.exception("Redis jest niedostępny dla blokady %s", bucket)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Ta funkcja jest chwilowo niedostępna. Spróbuj ponownie później.",
        ) from exc
    if not acquired:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Jedna operacja tego typu już trwa. Poczekaj na jej zakończenie.",
            headers={"Retry-After": "5"},
        )
    try:
        yield
    finally:
        try:
            await get_redis().eval(RELEASE_LOCK_SCRIPT, 1, key, token)
        except RedisError:
            logger.exception("Nie udało się zwolnić blokady Redis %s", bucket)


async def redis_healthcheck() -> bool:
    try:
        return bool(await get_redis().ping())
    except RedisError:
        return False
