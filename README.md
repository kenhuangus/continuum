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

## Auth & multi-tenant

| Env | Purpose |
|-----|---------|
| `CONTINUUM_API_KEYS` | Comma-separated keys; when set, API requires `X-API-Key` or `Bearer` (maps to `org_demo`) |
| `CONTINUUM_API_KEY_MAP` | JSON `{"key_a":"org_a","key_b":"org_b"}` — per-key org isolation |
| `CONTINUUM_AUTH_DISABLED=1` | Force open access for local demo |
| `CONTINUUM_RATE_LIMIT_RPM` | Per-key/IP requests per minute (default 60) |
| `DATABASE_URL` | `postgresql://…` selects Postgres store (optional: `pip install sqlalchemy "psycopg[binary]"`); else SQLite via `CONTINUUM_DB_PATH` |
| `CONTINUUM_MCP_API_KEY` | When auth is on, MCP tools resolve org from this key / `CONTINUUM_API_KEY_MAP` |

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

## Science (what we implement vs cite)

Continuum’s Memory OS is designed against agent-memory literature, with **honest** claims:

| Implemented | Inspired by (not a full paper reproduction) |
|-------------|-----------------------------------------------|
| Retrieve-then-pack (BM25 sparse ∪ ANN dense ∪ entity → budget pack) | Hybrid RAG + MemGPT-style context as RAM |
| Recency × importance × relevance re-rank | Park et al., *Generative Agents* (UIST 2023) |
| Slot supersession + 1-hop + Personalized PageRank expansion | HippoRAG-*style* graph (not full OpenIE pipeline) |
| Numpy IVF-lite ANN (optional `faiss` if installed) | Dense shortlist; brute-force for small N |
| Episodic→semantic `consolidate` job | Reflection / Storage→Reflection surveys |
| Eval: recall@budget, stale leakage, stress + LoCoMo-*style* fixtures | Synthetic offline suite — **not** official LoCoMo dump |

Research write-ups: [docs/research/AGENT_MEMORY_SURVEY.md](docs/research/AGENT_MEMORY_SURVEY.md), [MEMORY_ARCHITECTURE_V2.md](docs/research/MEMORY_ARCHITECTURE_V2.md), [IMPROVEMENT_PLAN.md](docs/research/IMPROVEMENT_PLAN.md), [LOOP3_NOTES.md](docs/research/LOOP3_NOTES.md). Assessment: [docs/MEMORY_SAAS_ASSESSMENT.md](docs/MEMORY_SAAS_ASSESSMENT.md).

Any coding agent can use Continuum as shared memory via **MCP** (`python -m continuum_mcp`) or **HTTP** (`/v1/memories`, `/v1/memories/pack_preview`, `/v1/memories/consolidate`) with **org + workspace** isolation and optional API keys.

## Honest scope

Science loops ship hybrid retrieve-then-pack (BM25 + ANN + PPR), RIR scoring, obsolescence-aware supersession, consolidate, org-scoped API keys, Postgres via `DATABASE_URL`, MCP stdio, and an offline eval suite (incl. LoCoMo-*style* fixtures) that beats a keyword-naive baseline. It is **not** production OAuth SaaS, and we do **not** claim full HippoRAG/MemGPT/Mem0 paper numbers or the official LoCoMo leaderboard.

## Deploy (Alibaba Cloud)

Containerize and deploy to Alibaba Cloud ECS for hackathon proof-of-deployment:

- **Guide:** [infra/README.md](infra/README.md) (ECS + Docker primary path, optional ACR)
- **Local smoke:** `docker compose up --build` or `.\infra\scripts\run-local.ps1`
- **Proof checklist:** [docs/PROOF_OF_ALIBABA_DEPLOYMENT.md](docs/PROOF_OF_ALIBABA_DEPLOYMENT.md)

## License

Apache-2.0 — see [LICENSE](LICENSE).
