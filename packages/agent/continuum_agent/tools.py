from __future__ import annotations

import json
from typing import Any

from continuum_memory.service import MemoryService


def memory_search(svc: MemoryService, workspace_id: str, query: str = "") -> list[dict]:
    return [m.model_dump(mode="json") for m in svc.search(workspace_id, query)]


def memory_remember(svc: MemoryService, memory: dict) -> dict:
    from continuum_memory.schemas import Memory

    m = Memory.model_validate(memory)
    stored = svc.remember(m)
    return stored.model_dump(mode="json")


def memory_forget(
    svc: MemoryService,
    memory_id: str,
    workspace_id: str | None = None,
    reason: str = "manual",
) -> dict:
    return svc.forget(memory_id, reason=reason, workspace_id=workspace_id)


def memory_list(svc: MemoryService, workspace_id: str, status: str | None = None) -> list[dict]:
    from continuum_memory.schemas import MemoryStatus

    st = MemoryStatus(status) if status else None
    return [m.model_dump(mode="json") for m in svc.list_memories(workspace_id, st)]


def memory_explain(svc: MemoryService, memory_id: str, workspace_id: str, query: str) -> str:
    return svc.explain(memory_id, workspace_id, query)


def memory_pack_preview(
    svc: MemoryService,
    workspace_id: str,
    query: str,
    budget: int = 1500,
    algorithm: str = "type_quota",
) -> dict:
    pack = svc.pack(workspace_id, query, budget, algorithm)
    return pack.model_dump(mode="json")


def dispatch_tool(svc: MemoryService, name: str, args: dict[str, Any]) -> str:
    """Execute a named memory tool and return JSON/text for the model."""
    try:
        if name == "memory_search":
            result: Any = memory_search(svc, args["workspace_id"], args.get("query", ""))
        elif name == "memory_remember":
            result = memory_remember(svc, args.get("memory", args))
        elif name == "memory_forget":
            result = memory_forget(
                svc,
                args["memory_id"],
                workspace_id=args.get("workspace_id"),
                reason=args.get("reason", "manual"),
            )
        elif name == "memory_list":
            result = memory_list(svc, args["workspace_id"], args.get("status"))
        elif name == "memory_explain":
            result = memory_explain(
                svc, args["memory_id"], args["workspace_id"], args.get("query", "")
            )
        elif name == "memory_pack_preview":
            result = memory_pack_preview(
                svc,
                args["workspace_id"],
                args.get("query", ""),
                int(args.get("budget", 1500)),
                args.get("algorithm", "type_quota"),
            )
        else:
            result = {"error": f"Unknown tool: {name}"}
    except Exception as exc:
        result = {"error": str(exc)}

    if isinstance(result, str):
        return result
    return json.dumps(result, default=str)


TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "memory_search",
            "description": "Search active memories in a workspace",
            "parameters": {
                "type": "object",
                "properties": {
                    "workspace_id": {"type": "string"},
                    "query": {"type": "string"},
                },
                "required": ["workspace_id", "query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "memory_remember",
            "description": "Explicitly store a memory",
            "parameters": {"type": "object", "properties": {"memory": {"type": "object"}}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "memory_forget",
            "description": "Forget a memory by id (workspace-scoped)",
            "parameters": {
                "type": "object",
                "properties": {
                    "memory_id": {"type": "string"},
                    "workspace_id": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["memory_id", "workspace_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "memory_list",
            "description": "List memories for a workspace",
            "parameters": {
                "type": "object",
                "properties": {
                    "workspace_id": {"type": "string"},
                    "status": {"type": "string"},
                },
                "required": ["workspace_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "memory_explain",
            "description": "Explain why a memory was included or excluded",
            "parameters": {
                "type": "object",
                "properties": {
                    "memory_id": {"type": "string"},
                    "workspace_id": {"type": "string"},
                    "query": {"type": "string"},
                },
                "required": ["memory_id", "workspace_id", "query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "memory_pack_preview",
            "description": "Preview packed context under a token budget",
            "parameters": {
                "type": "object",
                "properties": {
                    "workspace_id": {"type": "string"},
                    "query": {"type": "string"},
                    "budget": {"type": "integer"},
                    "algorithm": {"type": "string"},
                },
                "required": ["workspace_id", "query"],
            },
        },
    },
]
