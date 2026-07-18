# Continuum MCP server

Stdio MCP server exposing Continuum memory tools via `MemoryService`.

## Run

```bash
# From repo root (packages on PYTHONPATH via editable install)
pip install -e .
python -m continuum_mcp

# Optional official SDK
pip install -e ".[mcp]"
```

Console script: `continuum-mcp`.

## Tools

| Tool | Description |
|------|-------------|
| `memory_search` | Search active memories |
| `memory_remember` | Store a memory |
| `memory_forget` | Forget by id (requires `workspace_id`) |
| `memory_list` | List workspace memories |
| `memory_explain` | Explain pack inclusion |
| `memory_pack_preview` | Preview packed context |

Without the `mcp` package installed, the server runs a minimal JSON-RPC stdio loop (`initialize`, `tools/list`, `tools/call`).
