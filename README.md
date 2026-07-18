# Continuum — Memory Operating System for Agents

**Track 1 — MemoryAgent** · Global AI Hackathon Series with Qwen Cloud

Continuum accumulates typed memories across sessions, hybrid-retrieves candidates, packs under token budgets, forgets on purpose, and cites memory IDs.

## Quickstart

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

pip install -e ".[dev]"

copy .env.example .env          # Windows
# cp .env.example .env          # macOS/Linux
# Optional: DASHSCOPE_API_KEY / QWEN_API_KEY for live Qwen + embeddings
# Local demo: CONTINUUM_AUTH_DISABLED=1 (default in .env.example)

uvicorn continuum_api.main:app --reload --host 127.0.0.1 --port 8000
# Open http://127.0.0.1:8000/
```

## Auth

| Env | Purpose |
|-----|---------|
| `CONTINUUM_API_KEYS` | Comma-separated keys; when set, API requires `X-API-Key` or `Bearer` |
| `CONTINUUM_AUTH_DISABLED=1` | Force open access for local demo |
| `CONTINUUM_RATE_LIMIT_RPM` | Per-key/IP requests per minute (default 60) |

Health (`/v1/health`) and the static UI (`/`) stay open. Web UI has an optional API key field.

## MCP

```bash
python -m continuum_mcp
# or: continuum-mcp
# Optional: pip install -e ".[mcp]"
```

## Verify

```bash
pytest -m unit -q
pytest -m api -q
pytest -m eval -q

python evals/run_smoke.py
python evals/run_suite.py
# or: python -m continuum_eval   (with evals/ on PYTHONPATH)
```

## Monorepo layout

| Path | Purpose |
|------|---------|
| `packages/memory_core/` | Store, hybrid retrieve, embeddings, packer, forgetting |
| `packages/agent/` | Qwen client + agent loop |
| `apps/api/` | FastAPI REST API |
| `apps/web/` | Demo UI |
| `packages/mcp_server/` | MCP stdio server |
| `evals/` | Smoke + multi-fixture suite |
| `tests/` | `unit` / `api` / `e2e` / `eval` |

## API highlights

- `POST /v1/chat` — retrieve → pack → agent → ingest
- `GET /v1/memories` — inspector
- `GET /v1/memories/pack_preview` — packer panel
- `POST /v1/memories/{id}/forget?workspace_id=` — workspace-scoped forget
- `POST /v1/forgetting/run` — forgetting pass

## Honest scope

Phase A+ upgrade ships hybrid retrieve-then-pack, API keys, AuthZ on forget, real MCP stdio, and an offline eval suite. It is **not** a full multi-tenant cloud SaaS yet (SQLite primary; Postgres interface only). See [docs/MEMORY_SAAS_ASSESSMENT.md](docs/MEMORY_SAAS_ASSESSMENT.md).

## License

Apache-2.0 — see [LICENSE](LICENSE).
