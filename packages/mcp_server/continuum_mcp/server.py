"""Continuum MCP stdio server — tools wired to MemoryService."""

from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from typing import Any

from continuum_memory.schemas import Memory, MemoryStatus, MemoryType
from continuum_memory.service import MemoryService

TOOL_SCHEMAS = [
    {
        "name": "memory_search",
        "description": "Search memories in a workspace",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string"},
                "query": {"type": "string"},
            },
            "required": ["workspace_id"],
        },
    },
    {
        "name": "memory_remember",
        "description": "Store a memory",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string"},
                "content": {"type": "string"},
                "type": {"type": "string"},
                "entities": {"type": "array", "items": {"type": "string"}},
                "org_id": {"type": "string"},
            },
            "required": ["workspace_id", "content"],
        },
    },
    {
        "name": "memory_forget",
        "description": "Forget a memory by id (workspace-scoped)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "memory_id": {"type": "string"},
                "workspace_id": {"type": "string"},
                "reason": {"type": "string"},
            },
            "required": ["memory_id", "workspace_id"],
        },
    },
    {
        "name": "memory_list",
        "description": "List workspace memories",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string"},
                "status": {"type": "string"},
            },
            "required": ["workspace_id"],
        },
    },
    {
        "name": "memory_explain",
        "description": "Explain pack inclusion for a memory",
        "inputSchema": {
            "type": "object",
            "properties": {
                "memory_id": {"type": "string"},
                "workspace_id": {"type": "string"},
                "query": {"type": "string"},
            },
            "required": ["memory_id", "workspace_id", "query"],
        },
    },
    {
        "name": "memory_pack_preview",
        "description": "Preview packed context",
        "inputSchema": {
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
    {
        "name": "memory_consolidate",
        "description": "Consolidate episodic memories into distilled semantic memories",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string"},
                "max_groups": {"type": "integer"},
            },
            "required": ["workspace_id"],
        },
    },
]


def _svc() -> MemoryService:
    return MemoryService(db_path=os.environ.get("CONTINUUM_DB_PATH", "data/continuum.db"))


def _call_tool(name: str, arguments: dict[str, Any]) -> Any:
    svc = _svc()
    if name == "memory_search":
        return [
            m.model_dump(mode="json")
            for m in svc.search(arguments["workspace_id"], arguments.get("query", ""))
        ]
    if name == "memory_remember":
        now = datetime.now(timezone.utc)
        mem_type = MemoryType(arguments.get("type", "semantic"))
        mem = Memory(
            id=str(uuid.uuid4()),
            org_id=arguments.get("org_id", "org_demo"),
            workspace_id=arguments["workspace_id"],
            type=mem_type,
            content=arguments["content"],
            entities=list(arguments.get("entities") or []),
            created_at=now,
            last_accessed_at=now,
            source={"source": "mcp"},
        )
        return svc.remember(mem).model_dump(mode="json")
    if name == "memory_forget":
        return svc.forget(
            arguments["memory_id"],
            reason=arguments.get("reason", "mcp"),
            workspace_id=arguments["workspace_id"],
        )
    if name == "memory_list":
        st = MemoryStatus(arguments["status"]) if arguments.get("status") else None
        return [
            m.model_dump(mode="json")
            for m in svc.list_memories(arguments["workspace_id"], st)
        ]
    if name == "memory_explain":
        return svc.explain(
            arguments["memory_id"],
            arguments["workspace_id"],
            arguments.get("query", ""),
        )
    if name == "memory_pack_preview":
        pack = svc.pack(
            arguments["workspace_id"],
            arguments.get("query", ""),
            int(arguments.get("budget", 1500)),
            arguments.get("algorithm", "type_quota"),
        )
        return pack.model_dump(mode="json")
    if name == "memory_consolidate":
        written = svc.consolidate(
            arguments["workspace_id"],
            max_groups=int(arguments.get("max_groups", 20)),
        )
        return {
            "written": [m.model_dump(mode="json") for m in written],
            "count": len(written),
        }
    raise ValueError(f"Unknown tool: {name}")


def _try_sdk_main() -> bool:
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        try:
            from mcp.server import FastMCP  # type: ignore
        except ImportError:
            return False

    mcp = FastMCP("continuum")

    @mcp.tool()
    def memory_search(workspace_id: str, query: str = "") -> str:
        return json.dumps(
            _call_tool("memory_search", {"workspace_id": workspace_id, "query": query})
        )

    @mcp.tool()
    def memory_remember(
        workspace_id: str,
        content: str,
        type: str = "semantic",
        entities: list[str] | None = None,
        org_id: str = "org_demo",
    ) -> str:
        return json.dumps(
            _call_tool(
                "memory_remember",
                {
                    "workspace_id": workspace_id,
                    "content": content,
                    "type": type,
                    "entities": entities or [],
                    "org_id": org_id,
                },
            )
        )

    @mcp.tool()
    def memory_forget(memory_id: str, workspace_id: str, reason: str = "mcp") -> str:
        return json.dumps(
            _call_tool(
                "memory_forget",
                {"memory_id": memory_id, "workspace_id": workspace_id, "reason": reason},
            )
        )

    @mcp.tool()
    def memory_list(workspace_id: str, status: str | None = None) -> str:
        args: dict[str, Any] = {"workspace_id": workspace_id}
        if status:
            args["status"] = status
        return json.dumps(_call_tool("memory_list", args))

    @mcp.tool()
    def memory_explain(memory_id: str, workspace_id: str, query: str) -> str:
        return str(
            _call_tool(
                "memory_explain",
                {"memory_id": memory_id, "workspace_id": workspace_id, "query": query},
            )
        )

    @mcp.tool()
    def memory_pack_preview(
        workspace_id: str,
        query: str,
        budget: int = 1500,
        algorithm: str = "type_quota",
    ) -> str:
        return json.dumps(
            _call_tool(
                "memory_pack_preview",
                {
                    "workspace_id": workspace_id,
                    "query": query,
                    "budget": budget,
                    "algorithm": algorithm,
                },
            )
        )

    @mcp.tool()
    def memory_consolidate(workspace_id: str, max_groups: int = 20) -> str:
        return json.dumps(
            _call_tool(
                "memory_consolidate",
                {"workspace_id": workspace_id, "max_groups": max_groups},
            )
        )

    mcp.run(transport="stdio")
    return True


def _jsonrpc_loop() -> None:
    """Minimal JSON-RPC 2.0 MCP-compatible stdio loop (tools/list + tools/call)."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue

        req_id = msg.get("id")
        method = msg.get("method", "")
        params = msg.get("params") or {}

        if method == "initialize":
            result: Any = {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "continuum", "version": "0.2.0"},
            }
        elif method == "notifications/initialized":
            continue
        elif method in ("tools/list", "tools/listChanged"):
            result = {"tools": TOOL_SCHEMAS}
        elif method == "tools/call":
            name = params.get("name", "")
            arguments = params.get("arguments") or {}
            try:
                out = _call_tool(name, arguments)
                text = out if isinstance(out, str) else json.dumps(out, default=str)
                result = {"content": [{"type": "text", "text": text}]}
            except Exception as exc:
                result = {
                    "content": [{"type": "text", "text": json.dumps({"error": str(exc)})}],
                    "isError": True,
                }
        elif method == "ping":
            result = {}
        else:
            err = {"code": -32601, "message": f"Method not found: {method}"}
            sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": req_id, "error": err}) + "\n")
            sys.stdout.flush()
            continue

        if req_id is not None:
            sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": req_id, "result": result}) + "\n")
            sys.stdout.flush()


def main() -> None:
    if "--schemas" in sys.argv:
        print(json.dumps({"tools": TOOL_SCHEMAS}, indent=2))
        return
    if _try_sdk_main():
        return
    _jsonrpc_loop()


if __name__ == "__main__":
    main()
