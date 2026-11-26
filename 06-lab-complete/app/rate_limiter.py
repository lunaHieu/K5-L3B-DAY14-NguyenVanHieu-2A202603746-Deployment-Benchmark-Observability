"""Atomic, Redis backed sliding window rate limit per API key."""
import hashlib
import time
import uuid

import redis
from fastapi import HTTPException

from app.config import settings
from app.redis_client import r


WINDOW_SECONDS = 60

# A single script prevents two workers from admitting requests past the limit.
_CHECK_AND_ADD = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
redis.call('ZREMRANGEBYSCORE', key, '-inf', now - window)
local count = redis.call('ZCARD', key)
if count >= limit then
    local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
    local retry = math.max(1, math.ceil(tonumber(oldest[2]) + window - now))
    return {0, retry}
end
redis.call('ZADD', key, now, ARGV[4])
redis.call('EXPIRE', key, math.ceil(window) + 1)
return {1, limit - count - 1}
"""


def check_rate_limit(key: str) -> None:
    """Allow at most RATE_LIMIT_PER_MINUTE requests in any 60 second window."""
    key_hash = hashlib.sha256(key.encode("utf-8")).hexdigest()
    redis_key = f"agent:rate:{key_hash}"
    try:
        allowed, value = r.eval(
            _CHECK_AND_ADD, 1, redis_key, time.time(), WINDOW_SECONDS,
            settings.rate_limit_per_minute, uuid.uuid4().hex,
        )
    except redis.RedisError as exc:
        raise HTTPException(status_code=503, detail="Rate limiter unavailable") from exc
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(value), "X-RateLimit-Remaining": "0"},
        )
