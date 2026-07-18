from __future__ import annotations

import hashlib
import json
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


def _api_key_org_map() -> dict[str, str]:
    """Parse CONTINUUM_API_KEY_MAP='{"key_a":"org_a","key_b":"org_b"}'."""
    raw = os.environ.get("CONTINUUM_API_KEY_MAP", "")
    if not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Invalid CONTINUUM_API_KEY_MAP JSON; ignoring")
        return {}
    if not isinstance(parsed, dict):
        return {}
    return {str(k): str(v) for k, v in parsed.items()}


def _api_key_roles() -> dict[str, dict[str, str]]:
    """Parse CONTINUUM_API_KEY_ROLES='{"key":{"org":"org_a","role":"reader"}}'.

    Roles: reader | writer | admin. Lightweight env-map RBAC — not OAuth.
    """
    raw = os.environ.get("CONTINUUM_API_KEY_ROLES", "")
    if not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Invalid CONTINUUM_API_KEY_ROLES JSON; ignoring")
        return {}
    if not isinstance(parsed, dict):
        return {}
    out: dict[str, dict[str, str]] = {}
    for k, v in parsed.items():
        if isinstance(v, dict):
            role = str(v.get("role", "writer")).lower()
            if role not in ("reader", "writer", "admin"):
                role = "writer"
            out[str(k)] = {
                "org": str(v.get("org", "org_demo")),
                "role": role,
            }
        elif isinstance(v, str):
            out[str(k)] = {"org": "org_demo", "role": str(v).lower()}
    return out


def _valid_api_keys() -> set[str]:
    raw = os.environ.get("CONTINUUM_API_KEYS", "")
    keys = {k.strip() for k in raw.split(",") if k.strip()}
    keys.update(_api_key_org_map().keys())
    keys.update(_api_key_roles().keys())
    return keys


def _resolve_org_id(api_key: str | None) -> str:
    """Resolve org for an authenticated key: ROLES map, KEY_MAP, else org_demo."""
    if api_key:
        roles = _api_key_roles()
        if api_key in roles:
            return roles[api_key].get("org") or "org_demo"
        org = _api_key_org_map().get(api_key)
        if org:
            return org
    return "org_demo"


def _resolve_role(api_key: str | None) -> str:
    """Resolve RBAC role.

    Keys listed in CONTINUUM_API_KEY_ROLES use that role. Keys only in
    CONTINUUM_API_KEYS / CONTINUUM_API_KEY_MAP default to **admin** so Loop 3
    forget/IDOR behavior is preserved when roles are not configured.
    """
    if api_key:
        roles = _api_key_roles()
        if api_key in roles:
            return roles[api_key].get("role") or "writer"
    return "admin"


def _resolve_request_org(request: Request, body_org_id: str | None) -> str:
    """Resolve the effective org_id for a request.

    When auth is enabled, `request.state.org_id` (set by AuthRateLimitMiddleware
    from the caller's API key) is authoritative. An explicit `org_id` in the
    request body/query is only allowed if it matches — otherwise 403. When auth
    is disabled (local/demo mode), the caller-provided org_id (or "org_demo")
    is trusted as-is, preserving pre-multi-tenant behavior.
    """
    resolved = getattr(request.state, "org_id", None)
    if resolved is not None:
        if body_org_id is not None and body_org_id != resolved:
            raise HTTPException(
                status_code=403,
                detail="org_id does not match the organization bound to this API key",
            )
        return resolved
    return body_org_id or "org_demo"


def _require_role(request: Request, *allowed: str) -> None:
    """Enforce lightweight role when auth is enabled; no-op in demo mode."""
    if _auth_disabled():
        return
    role = getattr(request.state, "role", None) or "writer"
    if role not in allowed:
        raise HTTPException(
            status_code=403,
            detail=f"Role '{role}' is not permitted for this operation",
        )


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
            request.state.org_id = _resolve_org_id(api_key)
            request.state.role = _resolve_role(api_key)
        else:
            request.state.org_id = None
            request.state.role = "admin"

        bucket = api_key or (request.client.host if request.client else "anon")
        rpm = _rate_limit_rpm()
        if not _rate_limiter.allow(str(bucket), rpm):
            return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})

        return await call_next(request)


app.add_middleware(RequestIdMiddleware)
app.add_middleware(AuthRateLimitMiddleware)


class ChatRequest(BaseModel):
    org_id: str | None = None
    workspace_id: str
    session_id: str
    message: str
    memory_token_budget: int = 1500
    packer: str = "type_quota"


class RememberRequest(BaseModel):
    org_id: str | None = None
    workspace_id: str
    type: MemoryType = MemoryType.SEMANTIC
    content: str
    entities: list[str] = Field(default_factory=list)
    confidence: float = 0.9
    slots: dict[str, Any] = Field(default_factory=dict)


class ConsolidateRequest(BaseModel):
    org_id: str | None = None
    workspace_id: str
    max_groups: int = 20


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
    _require_role(request, "writer", "admin")
    idem = request.headers.get("Idempotency-Key")
    cached = _idempotency_get(idem)
    if cached is not None:
        return cached

    org = _resolve_request_org(request, req.org_id)

    pack = memory_service.pack(
        req.workspace_id,
        req.message,
        req.memory_token_budget,
        req.packer,
        org_id=org,
    )
    reply, citations = agent.reply(req.workspace_id, req.session_id, req.message, pack)
    written = memory_service.ingest_turn(
        req.workspace_id,
        req.session_id,
        req.message,
        reply,
        org_id=org,
    )
    result = {
        "reply": reply,
        "memories_packed": [m.model_dump(mode="json") for m in pack.memories],
        "pack_meta": {
            "token_estimate": pack.token_estimate,
            "algorithm": pack.algorithm,
            "budget_tokens": pack.budget_tokens,
            "explanations": pack.explanations,
            "explanation_details": pack.explanation_details,
            "candidate_count": pack.candidate_count,
        },
        "memories_written": [m.model_dump(mode="json") for m in written],
        "citations": citations,
    }
    _idempotency_set(idem, result)
    return result


@app.get("/v1/memories")
def list_memories(
    request: Request,
    workspace_id: str = Query(...),
    status: str | None = Query(None),
    q: str | None = Query(None),
    as_of: str | None = Query(None),
    org_id: str | None = Query(None),
) -> dict:
    _require_role(request, "reader", "writer", "admin")
    org = _resolve_request_org(request, org_id)
    as_of_dt = None
    if as_of:
        from datetime import datetime

        as_of_dt = datetime.fromisoformat(as_of)
    if q:
        items = memory_service.search(workspace_id, q, org_id=org)
    else:
        st = MemoryStatus(status) if status else None
        items = memory_service.list_memories(workspace_id, st, as_of=as_of_dt, org_id=org)
    return {"memories": [m.model_dump(mode="json") for m in items]}


@app.post("/v1/memories")
def create_memory(req: RememberRequest, request: Request) -> dict:
    from datetime import datetime, timezone

    _require_role(request, "writer", "admin")
    idem = request.headers.get("Idempotency-Key")
    cached = _idempotency_get(idem)
    if cached is not None:
        return cached

    now = datetime.now(timezone.utc)
    mem_id = str(uuid.uuid4())
    if idem:
        mem_id = str(uuid.UUID(hashlib.sha256(idem.encode()).hexdigest()[:32]))

    org = _resolve_request_org(request, req.org_id)
    mem = Memory(
        id=mem_id,
        org_id=org,
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
    request: Request,
    workspace_id: str = Query(...),
    query: str = Query(""),
    budget: int = Query(1500),
    algorithm: str = Query("type_quota"),
    as_of: str | None = Query(None),
    org_id: str | None = Query(None),
) -> dict:
    _require_role(request, "reader", "writer", "admin")
    org = _resolve_request_org(request, org_id)
    as_of_dt = None
    if as_of:
        from datetime import datetime

        as_of_dt = datetime.fromisoformat(as_of)
    pack = memory_service.pack(workspace_id, query, budget, algorithm, as_of=as_of_dt, org_id=org)
    return pack.model_dump(mode="json")


@app.get("/v1/memories/explain")
def explain_memory(
    request: Request,
    memory_id: str = Query(...),
    workspace_id: str = Query(...),
    query: str = Query(""),
    budget: int = Query(1500),
    org_id: str | None = Query(None),
) -> dict:
    """Structured pack-inclusion explain with lexical cite_overlap."""
    _require_role(request, "reader", "writer", "admin")
    org = _resolve_request_org(request, org_id)
    result = memory_service.explain(
        memory_id,
        workspace_id,
        query,
        budget_tokens=budget,
        org_id=org,
        structured=True,
    )
    if isinstance(result, dict):
        return result
    return {"explanation": result, "cite_overlap": 0.0, "details": {}}


@app.post("/v1/memories/consolidate")
def consolidate_memories(req: ConsolidateRequest, request: Request) -> dict:
    _require_role(request, "writer", "admin")
    org = _resolve_request_org(request, req.org_id)
    written = memory_service.consolidate(req.workspace_id, max_groups=req.max_groups, org_id=org)
    return {
        "written": [m.model_dump(mode="json") for m in written],
        "count": len(written),
    }


@app.get("/v1/memories/{memory_id}")
def get_memory(
    memory_id: str,
    request: Request,
    workspace_id: str = Query(...),
    org_id: str | None = Query(None),
) -> dict:
    _require_role(request, "reader", "writer", "admin")
    org = _resolve_request_org(request, org_id)
    mem = memory_service.get(memory_id, workspace_id=workspace_id, org_id=org)
    if not mem:
        raise HTTPException(status_code=404, detail="Memory not found")
    return mem.model_dump(mode="json")

@app.post("/v1/memories/{memory_id}/forget")
def forget_memory(
    memory_id: str,
    request: Request,
    workspace_id: str = Query(...),
    reason: str = Query("manual"),
    org_id: str | None = Query(None),
) -> dict:
    _require_role(request, "admin")
    org = _resolve_request_org(request, org_id)
    result = memory_service.forget(memory_id, reason=reason, workspace_id=workspace_id, org_id=org)
    if not result.get("forgotten"):
        if result.get("hitl_required"):
            return result
        raise HTTPException(status_code=404, detail="Memory not found")
    return result


@app.post("/v1/forgetting/run")
def run_forgetting(
    request: Request,
    workspace_id: str = Query(...),
    org_id: str | None = Query(None),
) -> dict:
    _require_role(request, "admin")
    org = _resolve_request_org(request, org_id)
    events = memory_service.run_forgetting_pass(workspace_id, org_id=org)
    return {"events": events, "count": len(events)}


if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

    @app.get("/")
    def web_index() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html")
