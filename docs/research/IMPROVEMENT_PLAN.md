# Continuum Memory OS — Executable Improvement Plan

**Audience:** Any coding agent (Cursor, Claude, Agy, Grok, Copilot, etc.)  
**Basis:** [`AGENT_MEMORY_SURVEY.md`](./AGENT_MEMORY_SURVEY.md)  
**Architecture:** [`MEMORY_ARCHITECTURE_V2.md`](./MEMORY_ARCHITECTURE_V2.md)  
**Date:** 2026-07-18

---

## Goals

1. Make retrieval scoring **literature-aligned** (Generative Agents R×I×R).  
2. Keep **retrieve-then-pack** as the only pack path; cap/index candidates.  
3. Ship a **real consolidation stub** (episodic → semantic).  
4. Expose Continuum as **shared memory SaaS substrate** via MCP + HTTP.  
5. Gate quality with **eval metrics** Continuum must beat naive baselines.  
6. Stay science-honest: only document what code does.

---

## Architecture changes (summary)

```
ingest → extract(+critic) → normalize/slots → supersession → [optional graph edges]
                                                              ↓
retrieve: sparse ∪ dense ∪ entity  →  score(R,I,Rel)  →  top_k candidates
                                                              ↓
pack(greedy|type_quota|knapsack_dp|mmr) under budget → cite IDs → agent
                                                              ↓
access bump utility / last_accessed
                                                              ↓
forget pass | consolidate(workspace) distill episodic→semantic
```

---

## File-level tasks

### Loop 1 — P0 (must land)

| ID | File(s) | Task | Done when |
|----|---------|------|-----------|
| L1.1 | `packages/memory_core/continuum_memory/scoring.py` (**new**) | Implement `recency_score`, `importance_score`, `relevance_score`, `combined_rir_score` with min-max normalize; decay 0.995 per hour | Unit tests pass |
| L1.2 | `retrieve.py`, `packer.py` | Use RIR for candidate ranking and pack `_score`; keep type boost as small additive prior | Pack explanations mention r/i/rel |
| L1.3 | `schemas.py`, `store.py` | Add optional `importance: float` (default from type prior); persist if column missing migrate gracefully | Round-trip store |
| L1.4 | `consolidate.py` (**new**), `service.py` | `MemoryService.consolidate(workspace_id)` groups active episodics by top entity; writes semantic distill; marks sources with policy tag `consolidated` (do not hard-delete) | Unit test |
| L1.5 | `graph.py` (**new**, minimal) | Edge model `MemoryEdge(src, dst, rel)` in SQLite; on remember, link shared entities + supersedes; `expand_neighbors` 1-hop into retrieve merge | Unit test |
| L1.6 | `apps/api/.../main.py` | `POST /v1/memories/consolidate`, ensure pack_preview returns score breakdown if available | API test |
| L1.7 | `packages/mcp_server/.../server.py` | Tools: `memory_consolidate`, `memory_pack_preview` (exists), auth via `CONTINUUM_API_KEYS` when set | MCP schema lists tools |
| L1.8 | `evals/continuum_eval/` | Ablations + metrics: recall@budget, stale_leakage; `rir` vs `no_rir`; Continuum ≥ naive | `run_suite.py` PASS |
| L1.9 | `tests/unit/test_scoring_rir.py`, `test_consolidate.py`, `test_graph.py` | Cover scoring math, consolidate, 1-hop | pytest -m unit |
| L1.10 | Docs | Update assessment “Progress after upgrade”, README science section | Accurate claims |

### Loop 2 — next P0/P1 (if time)

| ID | Task |
|----|------|
| L2.1 | Inverted-index / BM25-lite for sparse (stop full substring on huge N) |
| L2.2 | Embedding cache table keyed by memory id + content hash |
| L2.3 | Ablation report JSON artifact under `evals/reports/` |
| L2.4 | MCP HTTP transport (optional) — stdio remains primary |

### Loop 4 — landed (2026-07-18)

| ID | Task | Honest claim |
|----|------|--------------|
| L4.1 | Optional LLM importance (`CONTINUUM_LLM_IMPORTANCE`) | Blend into `Memory.importance` — not Generative Agents reflection trees |
| L4.2 | Consolidate uses LLM client when present | Sync reflection-*style* stub — not Letta sleep-time queue |
| L4.3 | `policy.py` PII/retention stubs | Heuristic tags + pack exclude — not GDPR product |
| L4.4 | Structured explain + `cite_overlap` + HTTP `/v1/memories/explain` | Lexical overlap — not NLI faithfulness |
| L4.5 | As-of LoCoMo-*style* fixtures | Synthetic PIT — not official LoCoMo dump |
| L4.6 | `CONTINUUM_API_KEY_ROLES` reader/writer/admin | Env-map RBAC — not OAuth |

See [`LOOP4_NOTES.md`](./LOOP4_NOTES.md).

### Loop 5 — landed (2026-07-18)

| ID | Task | Honest claim |
|----|------|--------------|
| L5.1 | Heuristic `faithfulness_score` + pack soft-demote | Not NLI entailment |
| L5.2 | Injection detect/quarantine + turn-level tag | Pattern quarantine — not full guardrail |
| L5.3 | `record_outcome` / `POST /v1/memories/outcome` | Labeled writeback — not RL |
| L5.4 | Async consolidate sleep worker | In-process thread — not Celery |
| L5.5 | Temporal supersedes-chain expand | Chain walk — not temporal KG |
| L5.6 | `/v1/openai/tools` + `/v1/chat/stream` SSE | Schema-compatible + SSE — not Chat Completions proxy |

See [`LOOP5_NOTES.md`](./LOOP5_NOTES.md).

---

## MCP / HTTP contracts (agents as clients)

### Auth

| Header | When |
|--------|------|
| `X-API-Key: <key>` or `Authorization: Bearer <key>` | Required if `CONTINUUM_API_KEYS` set and `CONTINUUM_AUTH_DISABLED` unset |
| `X-Request-Id` | Optional; echoed |
| `Idempotency-Key` | Optional on POST chat/memories |

Workspace isolation: every mutating call must pass `workspace_id`; forget/get scoped to workspace.

### HTTP endpoints (Memory SaaS surface)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/v1/health` | Liveness (open) |
| POST | `/v1/chat` | Agent turn with pack+ingest |
| GET | `/v1/memories?workspace_id=` | List |
| POST | `/v1/memories` | Remember |
| GET | `/v1/memories/pack_preview` | Retrieve+pack preview |
| POST | `/v1/memories/{id}/forget?workspace_id=` | Forget |
| POST | `/v1/forgetting/run` | Decay/expire pass |
| POST | `/v1/memories/consolidate` | **New** episodic→semantic distill |

### MCP tools

| Tool | Args | Maps to |
|------|------|---------|
| `memory_search` | workspace_id, query | search |
| `memory_remember` | workspace_id, content, type?, entities? | remember |
| `memory_forget` | memory_id, workspace_id, reason? | forget |
| `memory_list` | workspace_id, status? | list |
| `memory_pack_preview` | workspace_id, query, budget?, algorithm? | pack |
| `memory_explain` | memory_id, workspace_id, query | explain |
| `memory_consolidate` | workspace_id, max_groups? | consolidate |

Any external coding agent can treat Continuum as shared memory by pointing MCP at `python -m continuum_mcp` or HTTP at the API.

---

## Acceptance tests / metrics

### Automated gates

```bash
pytest -m "unit or api or eval" -q
python evals/run_suite.py
```

### Metrics (must report)

| Metric | Definition | Gate |
|--------|------------|------|
| **recall@budget** | Fraction of `must_include` substrings present in packed content under budget | Continuum ≥ naive_topk_keyword aggregate |
| **stale_leakage** | Fraction of `must_not_include` / superseded strings that still appear | Continuum ≤ naive |
| **candidate_cap** | `len(candidates) ≤ top_k*2` for large workspaces | Unit assert |
| **rir_ablation** | Continuum with RIR ≥ Continuum without RIR on recall *or* ≤ on stale (document either way; prefer ≥ recall) | Soft: report; hard: no regression vs naive |

### Honesty

- Do not assert HippoRAG / MemGPT / Mem0 paper numbers.  
- Local embed mode for CI (`CONTINUUM_FORCE_LOCAL_EMBED=1`).

---

## Implementation order for coding agents

1. `scoring.py` + unit tests  
2. Wire into `retrieve.py` / `packer.py`  
3. `graph.py` minimal + retrieve 1-hop  
4. `consolidate.py` + service + API + MCP  
5. Eval ablations  
6. Docs update  

**Do not** spend time on paid Alibaba free-tier workarounds.  
**Do not** commit secrets.

---

## Definition of done (Loop 1)

- [ ] RIR scoring in retrieve/pack  
- [ ] Consolidation endpoint + MCP tool  
- [ ] Minimal memory graph 1-hop  
- [ ] Eval suite PASS vs naive  
- [ ] Docs updated; claims match code  
