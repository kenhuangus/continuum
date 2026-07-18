from __future__ import annotations

import hashlib
import logging
import os
import time
import uuid
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Callable

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware

from continuum_agent.agent import ContinuumAgent
from continuum_agent.client import QwenClient
from continuum_memory.schemas import Memory, MemoryStatus, MemoryType
from continuum_memory.service import MemoryService

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("continuum.api")

WEB_DIR = Path(__file__).resolve().parents[2] / "web"
DB_PATH = os.environ.get("CONTINUUM_DB_PATH", "data/continuum.db")

memory_service = MemoryService(db_path=DB_PATH, client=QwenClient())
agent = ContinuumAgent(memory_service, client=QwenClient())

app = FastAPI(title="Continuum API", version="0.2.0")


def _cors_origins() -> list[str]:
    defaults = [
        "http://127.0.0.1:8000",
        "http://localhost:8000",
        "http://127.0.0.1:5500",
        "http://localhost:5500",
    ]
    extra = os.environ.get("CONTINUUM_CORS_ORIGINS", "")
    extras = [o.strip() for o in extra.split(",") if o.strip()]
    seen = set(defaults)
    merged = list(defaults)
    for origin in extras:
        if origin not in seen:
            merged.append(origin)
            seen.add(origin)
    return merged


app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _auth_disabled() -> bool:
    if os.environ.get("CONTINUUM_AUTH_DISABLED", "").lower() in ("1", "true", "yes"):
        return True
    # No keys configured → local demo mode (auth off). Setting CONTINUUM_API_KEYS enables auth.
    if not _valid_api_keys():
        return True
    return False


def _valid_api_keys() -> set[str]:
    raw = os.environ.get("CONTINUUM_API_KEYS", "")
    return {k.strip() for k in raw.split(",") if k.strip()}


def _extract_api_key(request: Request) -> str | None:
    key = request.headers.get("X-API-Key")
    if key:
        return key.strip()
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return None


def _rate_limit_rpm() -> int:
    try:
        return int(os.environ.get("CONTINUUM_RATE_LIMIT_RPM", "60"))
    except ValueError:
        return 60


class _RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, rpm: int) -> bool:
        now = time.time()
        window = self._hits[key]
        while window and now - window[0] > 60.0:
            window.popleft()
        if len(window) >= rpm:
            return False
        window.append(now)
        return True


_rate_limiter = _RateLimiter()
_idempotency_cache: dict[str, tuple[float, Any]] = {}
_IDEMPOTENCY_TTL = 300.0


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        req_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
        request.state.request_id = req_id
        response = await call_next(request)
        response.headers["X-Request-Id"] = req_id
        return response


class AuthRateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path
        if path in ("/v1/health", "/") or path.startswith("/static"):
            return await call_next(request)

        api_key = _extract_api_key(request)
        if not _auth_disabled():
            keys = _valid_api_keys()
            if not api_key or api_key not in keys:
                return JSONResponse(
                    status_code=401, content={"detail": "Invalid or missing API key"}
                )

        bucket = api_key or (request.client.host if request.client else "anon")
        rpm = _rate_limit_rpm()
        if not _rate_limiter.allow(str(bucket), rpm):
            return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})

        return await call_next(request)


app.add_middleware(RequestIdMiddleware)
app.add_middleware(AuthRateLimitMiddleware)


class ChatRequest(BaseModel):
    org_id: str = "org_demo"
    workspace_id: str
    session_id: str
    message: str
    memory_token_budget: int = 1500
    packer: str = "type_quota"


class RememberRequest(BaseModel):
    org_id: str = "org_demo"
    workspace_id: str
    type: MemoryType = MemoryType.SEMANTIC
    content: str
    entities: list[str] = Field(default_factory=list)
    confidence: float = 0.9
    slots: dict[str, Any] = Field(default_factory=dict)


def _idempotency_get(key: str | None) -> Any | None:
    if not key:
        return None
    entry = _idempotency_cache.get(key)
    if not entry:
        return None
    ts, payload = entry
    if time.time() - ts > _IDEMPOTENCY_TTL:
        _idempotency_cache.pop(key, None)
        return None
    return payload


def _idempotency_set(key: str | None, payload: Any) -> None:
    if not key:
        return
    _idempotency_cache[key] = (time.time(), payload)


@app.get("/v1/health")
def health() -> dict:
    return {"status": "ok", "service": "continuum", "db": DB_PATH}


@app.post("/v1/chat")
def chat(req: ChatRequest, request: Request) -> dict:
    idem = request.headers.get("Idempotency-Key")
    cached = _idempotency_get(idem)
    if cached is not None:
        return cached

    pack = memory_service.pack(
        req.workspace_id,
        req.message,
        req.memory_token_budget,
        req.packer,
    )
    reply, citations = agent.reply(req.workspace_id, req.session_id, req.message, pack)
    written = memory_service.ingest_turn(
        req.workspace_id,
        req.session_id,
        req.message,
        reply,
        org_id=req.org_id,
    )
    result = {
        "reply": reply,
        "memories_packed": [m.model_dump(mode="json") for m in pack.memories],
        "pack_meta": {
            "token_estimate": pack.token_estimate,
            "algorithm": pack.algorithm,
            "budget_tokens": pack.budget_tokens,
            "explanations": pack.explanations,
            "candidate_count": pack.candidate_count,
        },
        "memories_written": [m.model_dump(mode="json") for m in written],
        "citations": citations,
    }
    _idempotency_set(idem, result)
    return result


@app.get("/v1/memories")
def list_memories(
    workspace_id: str = Query(...),
    status: str | None = Query(None),
    q: str | None = Query(None),
    as_of: str | None = Query(None),
) -> dict:
    as_of_dt = None
    if as_of:
        from datetime import datetime

        as_of_dt = datetime.fromisoformat(as_of)
    if q:
        items = memory_service.search(workspace_id, q)
    else:
        st = MemoryStatus(status) if status else None
        items = memory_service.list_memories(workspace_id, st, as_of=as_of_dt)
    return {"memories": [m.model_dump(mode="json") for m in items]}


@app.post("/v1/memories")
def create_memory(req: RememberRequest, request: Request) -> dict:
    from datetime import datetime, timezone

    idem = request.headers.get("Idempotency-Key")
    cached = _idempotency_get(idem)
    if cached is not None:
        return cached

    now = datetime.now(timezone.utc)
    mem_id = str(uuid.uuid4())
    if idem:
        mem_id = str(uuid.UUID(hashlib.sha256(idem.encode()).hexdigest()[:32]))

    mem = Memory(
        id=mem_id,
        org_id=req.org_id,
        workspace_id=req.workspace_id,
        type=req.type,
        content=req.content,
        entities=req.entities,
        confidence=req.confidence,
        created_at=now,
        last_accessed_at=now,
        source={"source": "api"},
        slots=req.slots,
    )
    stored = memory_service.remember(mem)
    result = stored.model_dump(mode="json")
    _idempotency_set(idem, result)
    return result


@app.get("/v1/memories/pack_preview")
def pack_preview(
    workspace_id: str = Query(...),
    query: str = Query(""),
    budget: int = Query(1500),
    algorithm: str = Query("type_quota"),
    as_of: str | None = Query(None),
) -> dict:
    as_of_dt = None
    if as_of:
        from datetime import datetime

        as_of_dt = datetime.fromisoformat(as_of)
    pack = memory_service.pack(workspace_id, query, budget, algorithm, as_of=as_of_dt)
    return pack.model_dump(mode="json")


@app.get("/v1/memories/{memory_id}")
def get_memory(memory_id: str, workspace_id: str = Query(...)) -> dict:
    mem = memory_service.get(memory_id, workspace_id=workspace_id)
    if not mem:
        raise HTTPException(status_code=404, detail="Memory not found")
    return mem.model_dump(mode="json")

@app.post("/v1/memories/{memory_id}/forget")
def forget_memory(
    memory_id: str,
    workspace_id: str = Query(...),
    reason: str = Query("manual"),
) -> dict:
    result = memory_service.forget(memory_id, reason=reason, workspace_id=workspace_id)
    if not result.get("forgotten"):
        if result.get("hitl_required"):
            return result
        raise HTTPException(status_code=404, detail="Memory not found")
    return result


@app.post("/v1/forgetting/run")
def run_forgetting(workspace_id: str = Query(...)) -> dict:
    events = memory_service.run_forgetting_pass(workspace_id)
    return {"events": events, "count": len(events)}


if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

    @app.get("/")
    def web_index() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html")
