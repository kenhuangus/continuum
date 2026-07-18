"""In-process sleep-time consolidate worker stub.

Honest claim: threading + in-memory job table — not Letta durable sleep-time,
not Celery/RQ/Redis, not multi-replica safe.
"""

from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from typing import Any, Callable

logger = logging.getLogger("continuum.sleep_worker")

_LOCK = threading.Lock()
_JOBS: dict[str, dict[str, Any]] = {}
_WORKER_ENABLED_DEFAULT = True


def sleep_worker_enabled() -> bool:
    raw = os.environ.get("CONTINUUM_SLEEP_WORKER", "1").lower()
    return raw not in ("0", "false", "no", "off")


def get_job(job_id: str) -> dict[str, Any] | None:
    with _LOCK:
        job = _JOBS.get(job_id)
        return dict(job) if job else None


def list_jobs(limit: int = 50) -> list[dict[str, Any]]:
    with _LOCK:
        items = sorted(_JOBS.values(), key=lambda j: j.get("created_at", 0), reverse=True)
        return [dict(j) for j in items[:limit]]


def enqueue_consolidate(
    consolidate_fn: Callable[[], list[Any]],
    *,
    workspace_id: str,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Schedule consolidate_fn on a daemon thread; return job stub immediately."""
    if not sleep_worker_enabled():
        raise RuntimeError("sleep worker disabled (CONTINUUM_SLEEP_WORKER=0)")

    job_id = str(uuid.uuid4())
    now = time.time()
    job: dict[str, Any] = {
        "job_id": job_id,
        "workspace_id": workspace_id,
        "status": "pending",
        "created_at": now,
        "started_at": None,
        "finished_at": None,
        "written_count": 0,
        "error": None,
        "meta": meta or {},
    }
    with _LOCK:
        _JOBS[job_id] = job

    def _run() -> None:
        with _LOCK:
            cur = _JOBS.get(job_id)
            if not cur:
                return
            cur["status"] = "running"
            cur["started_at"] = time.time()
        try:
            written = consolidate_fn() or []
            with _LOCK:
                cur = _JOBS.get(job_id)
                if cur:
                    cur["status"] = "done"
                    cur["written_count"] = len(written)
                    cur["finished_at"] = time.time()
                    cur["written_ids"] = [
                        getattr(m, "id", None) or (m.get("id") if isinstance(m, dict) else None)
                        for m in written
                    ]
        except Exception as exc:
            logger.exception("sleep consolidate job %s failed", job_id)
            with _LOCK:
                cur = _JOBS.get(job_id)
                if cur:
                    cur["status"] = "error"
                    cur["error"] = str(exc)
                    cur["finished_at"] = time.time()

    t = threading.Thread(target=_run, name=f"continuum-sleep-{job_id[:8]}", daemon=True)
    t.start()
    return dict(job)
