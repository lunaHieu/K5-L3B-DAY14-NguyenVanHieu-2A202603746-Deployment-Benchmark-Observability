"""Daily LLM spending guard backed by Redis."""
import hashlib
from datetime import datetime, timedelta, timezone

import redis
from fastapi import HTTPException

from app.config import settings
from app.redis_client import r


PRICE_INPUT_PER_1K = 0.00015
PRICE_OUTPUT_PER_1K = 0.0006


def _cost_key(api_key: str) -> tuple[str, int]:
    now = datetime.now(timezone.utc)
    tomorrow = datetime.combine(now.date() + timedelta(days=1), datetime.min.time(), timezone.utc)
    ttl = max(1, int((tomorrow - now).total_seconds()) + 1)
    key_hash = hashlib.sha256(api_key.encode("utf-8")).hexdigest()
    return f"agent:cost:{now.date().isoformat()}:{key_hash}", ttl


def check_budget(api_key: str) -> None:
    """Check the current daily spend before calling the LLM."""
    key, _ = _cost_key(api_key)
    try:
        spent = float(r.get(key) or 0)
    except redis.RedisError as exc:
        raise HTTPException(status_code=503, detail="Cost guard unavailable") from exc
    if spent >= settings.daily_budget_usd:
        raise HTTPException(status_code=402, detail="Daily LLM budget exceeded")


def record_cost(api_key: str, input_tokens: int, output_tokens: int) -> float:
    """Record the estimated request cost and return it in USD."""
    cost = (input_tokens * PRICE_INPUT_PER_1K + output_tokens * PRICE_OUTPUT_PER_1K) / 1000
    key, ttl = _cost_key(api_key)
    try:
        with r.pipeline(transaction=True) as pipe:
            pipe.incrbyfloat(key, cost)
            pipe.expire(key, ttl)
            pipe.execute()
    except redis.RedisError as exc:
        raise HTTPException(status_code=503, detail="Cost guard unavailable") from exc
    return cost
