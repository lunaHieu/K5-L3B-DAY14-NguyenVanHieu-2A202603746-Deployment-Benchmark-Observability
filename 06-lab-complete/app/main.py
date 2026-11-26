"""Production AI agent with health, auth, Redis limits and JSON logging."""
import json
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from app.auth import verify_api_key
from app.config import settings
from app.cost_guard import check_budget, record_cost
from app.rate_limiter import check_rate_limit
from app.redis_client import r, redis_healthy
from utils.mock_llm import ask as llm_ask


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "lvl": record.levelname,
            "event": record.getMessage(),
        }
        for name in ("path", "status", "ms"):
            value = getattr(record, name, None)
            if value is not None:
                data[name] = value
        return json.dumps(data, ensure_ascii=False)


logger = logging.getLogger("agent")
logger.setLevel(logging.INFO)
logger.propagate = False
handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
logger.addHandler(handler)
started_at = time.monotonic()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("startup")
    yield
    # Uvicorn waits for accepted requests before entering lifespan shutdown.
    logger.info("shutdown")
    r.close()


app = FastAPI(title="Production AI Agent", lifespan=lifespan)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    started = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        logger.info(
            "request",
            extra={
                "path": request.url.path,
                "status": status,
                "ms": round((time.perf_counter() - started) * 1000, 2),
            },
        )


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)


@app.get("/health")
def health():
    """Liveness: report process status even if Redis is unavailable."""
    return {
        "status": "ok",
        "environment": settings.environment,
        "uptime_seconds": round(time.monotonic() - started_at, 2),
    }


@app.get("/ready")
def ready():
    """Readiness: route traffic only when Redis is reachable."""
    if not redis_healthy():
        raise HTTPException(status_code=503, detail="Redis unavailable")
    return {"ready": True}


@app.post("/ask")
def ask(body: AskRequest, api_key: str = Depends(verify_api_key)):
    """Serve a mock response after shared rate and cost checks."""
    check_rate_limit(api_key)
    check_budget(api_key)
    answer = llm_ask(body.question)
    # The mock provider does not report tokens; these are demo estimates.
    input_tokens = max(1, len(body.question.split()) * 2)
    output_tokens = max(1, len(answer.split()) * 2)
    request_cost = record_cost(api_key, input_tokens, output_tokens)
    return {"question": body.question, "answer": answer, "cost_usd": request_cost}
