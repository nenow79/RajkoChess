import hashlib
import hmac
import logging
import secrets
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import AsyncIterator, cast

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

ACQUIRE_SEMAPHORE_SCRIPT = """
local redis_time = redis.call('TIME')
local now_ms = (tonumber(redis_time[1]) * 1000) + math.floor(tonumber(redis_time[2]) / 1000)
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now_ms)

if redis.call('ZCARD', KEYS[1]) >= tonumber(ARGV[2]) then
  local earliest = redis.call('ZRANGE', KEYS[1], 0, 0, 'WITHSCORES')
  local retry_after = 1
  if earliest[2] then
    retry_after = math.max(1, math.ceil((tonumber(earliest[2]) - now_ms) / 1000))
  end
  return {0, retry_after}
end

local expires_at = now_ms + (tonumber(ARGV[3]) * 1000)
redis.call('ZADD', KEYS[1], expires_at, ARGV[1])
redis.call('EXPIRE', KEYS[1], tonumber(ARGV[3]))
return {1, 0}
"""

RELEASE_SEMAPHORE_SCRIPT = """
return redis.call('ZREM', KEYS[1], ARGV[1])
"""


class RateLimitStoreUnavailable(Exception):
    pass


@lru_cache
def get_redis() -> Redis:
    return Redis.from_url(
        get_settings().redis_url,
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
    )


async def _eval_script(script: str, key: str, *arguments: str) -> object:
    # redis-py 6.x types async eval as `str | Awaitable[str]`, although the
    # asyncio client always returns an awaitable. Keep the compatibility cast
    # in one place instead of suppressing Pyright at every call site.
    evaluate = cast(Callable[..., Awaitable[object]], get_redis().eval)
    return await evaluate(script, 1, key, *arguments)


def _redis_pair(value: object) -> tuple[object, object]:
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return value[0], value[1]
    raise RateLimitStoreUnavailable("Redis zwrócił nieprawidłowy wynik skryptu")


def _redis_int(value: object) -> int:
    if isinstance(value, (bytes, str, int, float)):
        return int(value)
    raise RateLimitStoreUnavailable("Redis zwrócił nieprawidłową liczbę")


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
        result = _redis_pair(
            await _eval_script(FIXED_WINDOW_SCRIPT, key, str(window_seconds))
        )
    except RedisError as exc:
        raise RateLimitStoreUnavailable from exc
    count, retry_after = _redis_int(result[0]), max(_redis_int(result[1]), 1)
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
            await _eval_script(RELEASE_LOCK_SCRIPT, key, token)
        except RedisError:
            logger.exception("Nie udało się zwolnić blokady Redis %s", bucket)


@asynccontextmanager
async def global_concurrency_slot(
    *, bucket: str, limit: int, ttl_seconds: int = 300
) -> AsyncIterator[None]:
    key = f"rajko:semaphore:{bucket}"
    token = secrets.token_urlsafe(24)
    try:
        result = _redis_pair(
            await _eval_script(
                ACQUIRE_SEMAPHORE_SCRIPT,
                key,
                token,
                str(limit),
                str(ttl_seconds),
            )
        )
        acquired, retry_after = result
    except RedisError as exc:
        logger.exception("Redis jest niedostępny dla globalnego limitu %s", bucket)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Ta funkcja jest chwilowo niedostępna. Spróbuj ponownie później.",
        ) from exc
    if not _redis_int(acquired):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Serwer wykonuje już maksymalną liczbę takich operacji. Spróbuj ponownie za chwilę.",
            headers={"Retry-After": str(max(_redis_int(retry_after), 1))},
        )
    try:
        yield
    finally:
        try:
            await _eval_script(RELEASE_SEMAPHORE_SCRIPT, key, token)
        except RedisError:
            logger.exception("Nie udało się zwolnić globalnego limitu Redis %s", bucket)


async def redis_healthcheck() -> bool:
    try:
        return bool(await get_redis().ping())
    except RedisError:
        return False
