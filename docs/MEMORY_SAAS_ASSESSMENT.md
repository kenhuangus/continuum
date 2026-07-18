# Continuum Memory System — Scientific & SaaS Assessment

**Date:** 2026-07-18  
**Scope:** Code as implemented (Phase A vertical slice) vs PRD ambition  
**Verdict:** **NOT YET** — neither scientifically solid enough for research-grade claims, nor SaaS-ready for arbitrary agents.

---

## Executive verdict

| Question | Answer |
|---|---|
| Scientifically solid? | **NOT YET** — sound *taxonomy sketch* and honest Phase A plumbing; retrieval/packing/forgetting/eval lack rigor vs literature and vs PRD claims |
| Cloud SaaS for all agents? | **NO** today — open unauthenticated API + SQLite + MCP stub; not multi-tenant production |

Phase A (docs/architecture.md, ADR 0001) correctly describes a demo slice. The PRD and marketing language claim hybrid retrieval, knapsack/MMR packers, MCP Memory OS, and research-grade evals that are **not implemented**.

---

## Scientific solidity

### Memory taxonomy — sound sketch, shallow operationalization

`MemoryType` in `packages/memory_core/continuum_memory/schemas.py` mirrors cognitive categories (episodic / semantic / preference / procedural / decision / artifact_ref). That mapping is directionally aligned with Tulving-style distinctions and agent-memory literature (MemGPT tiers, generative-agents reflection).

**Gaps:** types are labels only. There is no consolidation pipeline (working → episodic → semantic), no reflection/distillation, no procedural skill learning from outcomes. Heuristic extractor (`extractor.extract_heuristic`) is Acme-demo-specific regex (VIP, discount %, email). LLM path (`extract_with_llm`) is single-pass JSON with no critic. `policy_tags` exist on the schema but are unused for governance.

### Write path — light rigor

| Stage (PRD §10.2) | Implemented? |
|---|---|
| Extract | Yes — heuristic + optional LLM (`extractor.py`) |
| Normalize entities | Weak — CapWords + Acme hardcodes (`_extract_entities`) |
| Dedup / merge | Partial — exact normalize + Jaccard > 0.9 skip (`store.remember`) |
| Conflict / supersession | Heuristic topic+entity (`supersession._conflicts`) |
| Policy / PII | No |
| Embed + index | No |
| Audit on write | Forget audit only |

Supersession is rule-based (shared type + entity overlap + topic keywords: discount/vip/email/sla/price). False positives (two unrelated Acme semantic facts) and false negatives (paraphrases without keyword topics) are expected. No NLI, no structured slot conflict (e.g. `discount_pct`), no multi-hop contradiction graph.

`schemas.Memory.supersedes` is a single optional `str`; PRD models a list — limits multi-supersession history.

### Retrieval — keyword scan, not hybrid

`MemoryStore.search` loads all active workspace rows and substring/token-matches content+entities. No dense embeddings, no BM25/sparse index, no vector store. Packing (`MemoryService.pack`) scores the **full active list**, not a retrieved candidate set — O(n) and non-scalable.

Vs literature: far below RAG hybrid (dense+sparse), MemGPT paging, HippoRAG graph retrieval, generative-agents retrieval by embedding+recency+importance. Type priors in `_score` are a useful engineering heuristic, not a retrieval system.

### Context packing — budget-aware heuristics, not optimality

Implemented: `pack_greedy`, `pack_type_quota` (`packer.py`). Token estimate = `len(text)//4`. Score = utility×confidence + keyword hits + type boost.

**Not implemented** despite PRD §10.4: `knapsack_dp`, `mmr`, `as_of`. Claims of “optimal / near-optimal knapsack” are unsupported. Type-quota is a sensible decision-grade bias for the demo, not proven optimal.

### Forgetting — pragmatic stubs

`ForgettingEngine.run_pass`: expire on `effective_to`; decay confidence after 30 unused days; forget below threshold. Manual forget + audit log. Supersession retires conflicts.

Missing vs PRD/cognitive science: utility cull under storage pressure, policy retention (PII), HITL gates, cold archive, Ebbinghaus-style scheduling, reinforcement from outcomes. Decay is linear and arbitrary (`decay_factor=0.05`), not empirically tuned.

### Evaluation — smoke only

`evals/run_smoke.py` + one fixture (`acme_session_a_b.json`): Session A ingest → pack Session B → assert substrings `12%`, `discount`, `vip`, `email` under budget 400. Unit tests cover store/packer/supersession; API isolation by `workspace_id` only.

**Missing for “increasingly accurate” / research claims:** ≥50 scenarios, baselines (no-memory, full-history, RAG), critical-fact recall@budget, stale leakage after supersession, contradiction F1, ablations, LLM-as-judge, adversarial injection suite (PRD E1–E8). Cannot claim measurable improvement over time.

### Known failure modes (code-backed)

| Failure | Mechanism |
|---|---|
| Hallucinated memories | Single-pass LLM extract; no critic; heuristic false positives on non-Acme text |
| Memory poisoning / prompt injection | Stored content injected into agent context (`agent.reply` context_block); no sanitization or untrusted-memory policy |
| Duplication | Near-dup Jaccard helps; semantic paraphrases and cross-type dups can remain |
| Stale leakage | Supersession helps on keyword conflicts; packer does not hard-exclude superseded (status filter does); expired memories only cleared on explicit forgetting pass |
| Cross-workspace IDOR | Forget by `memory_id` with no workspace/auth check (`main.forget_memory`) |
| Org isolation absent | Queries filter `workspace_id` only; `org_id` stored but unused in search/list |

UI XSS: `apps/web/index.html` uses `textContent` for user/memory content (good partial mitigation).

---

## SaaS readiness for “all agents”

| Capability | Status |
|---|---|
| Multi-tenancy / isolation | Workspace string filter only; shared SQLite file; no org RBAC |
| AuthN/AuthZ, API keys, quotas | **None** — FastAPI endpoints are open |
| Scalability | SQLite Phase A (ADR 0001); full-table search; no Redis/Tablestore |
| Latency SLOs | Unmeasured; pack/search scan all actives |
| MCP / OpenAI-compatible / SDK | MCP is schema stub (`continuum_mcp/server.py` prints JSON and exits); agent tools exist in-process only; no public SDK packaging story beyond monorepo |
| Observability / audit / compliance | Forget audit table; no traces, metrics, PII retention, GDPR erase-by-subject, export |
| Reliability | No idempotency keys, retries, DLQ, backups |
| Billing / metering | None |
| Security | Open write/forget; injection via memory; CORS allows `"null"` |

**PRD vs Phase A gap:** PRD describes Memory OS on Alibaba with hybrid index, Redis working memory, MCP stdio+HTTP, admin API keys, multimodal ingest, eval leaderboard. Implemented: local SQLite + REST chat/memories + greedy/type_quota pack + heuristic forget + MCP skeleton + smoke eval. Architecture docs honestly say “Later phases” for hybrid/MCP/deploy.

---

## Prioritized roadmap

### P0 — Scientific credibility blockers

1. **Hybrid retrieval** — embeddings + sparse/BM25 + entity filter; retrieve then pack (stop full-table score).
2. **Structured conflict model** — slot/key conflicts for decisions (discount %, VIP flag) before topic heuristics; multi-link supersession.
3. **Extractor quality** — multi-pass extract+critic; reject questions as writes; domain-agnostic schemas.
4. **Eval suite** — fixtures with baselines; recall@budget, stale leakage, contradiction F1; CI gates.
5. **Honest product claims** — align README/PRD marketing with Phase A until above lands.

### P1 — SaaS blockers

1. AuthN (API keys / OAuth) + AuthZ (org/workspace scopes) on every route and MCP tool.
2. Managed store abstraction (Postgres/Tablestore) + per-tenant isolation; retire single-file SQLite for prod.
3. Real MCP stdio/HTTP server wired to `MemoryService` (replace stub).
4. Quotas, rate limits, idempotent writes (`Idempotency-Key`), soft-delete + hard purge APIs.
5. Observability (trace IDs, pack fill, hit/miss) + backup/PITR.
6. Memory-injection hardening (trust tiers, tool allowlists, content scanning).

### P2 — Differentiators

1. Knapsack DP + MMR + as-of packers with faithfulness evals.
2. Utility learning from outcomes; working-memory consolidation.
3. Policy engine (TTL/PII/region); cold archive; HITL forget.
4. Billing meters (writes, retrieves, packed tokens).
5. OpenAI-compatible memory plugin / SDK for arbitrary agents.

---

## Bottom line

Continuum Phase A is a **credible demo substrate** for Track-1 storytelling (typed memories, budget packing, supersession, citations). It is **not** yet a scientifically rigorous memory system relative to RAG/MemGPT/HippoRAG-class work, and it is **not** a multi-tenant Memory SaaS for all agents. Path forward is clear: retrieval + eval (P0), then tenancy/auth/MCP/store (P1), then packer/policy/billing differentiation (P2).

---

## Progress after upgrade (P0+P1)

**Date:** 2026-07-18 (post-upgrade)

### Closed

| Item | Status |
|------|--------|
| Hybrid retrieve-then-pack | **Shipped** — sparse + local/API embeddings; `MemoryService.pack` packs candidates only |
| Slot supersession + `supersedes: list[str]` | **Shipped** — `slots` on Memory; multi-id append on mark_superseded |
| Domain-agnostic extractor + interrogative reject + LLM critic | **Shipped** — heuristic CapWords patterns; `critique_memories` when LLM available |
| Eval suite ≥15 fixtures + baselines | **Shipped** — `evals/run_suite.py`, `evals/continuum_eval/` |
| API key auth + rate limit + request id | **Shipped** — `CONTINUUM_API_KEYS` / `CONTINUUM_AUTH_DISABLED` / RPM |
| Forget AuthZ (workspace scope) | **Shipped** — wrong workspace → 404 |
| Real MCP stdio | **Shipped** — JSON-RPC loop; optional `mcp` SDK |
| Idempotency-Key (chat/memories POST) | **Shipped** — in-memory TTL cache |
| Injection sanitize on packed context | **Shipped** |
| Packer knapsack_dp / mmr + as_of filter | **Shipped** (basic) |
| Store protocol | **Shipped** — SQLite impl; Postgres stub/interface only |

### Still open

| Item | Gap |
|------|-----|
| Postgres / Tablestore prod store | Interface only; SQLite remains the working path |
| OAuth / full multi-tenant SaaS | API keys only |
| BM25 / vector DB index | In-process hybrid over workspace rows; not scaled |
| NLI / faithfulness critic | Heuristic + optional LLM critic, not research-grade |
| Billing meters, PITR, policy engine | Not started |
| HITL forget | Env-gated flag only |

**Updated verdict:** Scientifically **stronger** than Phase A (retrieval + eval + slots) but still short of literature-grade memory systems. SaaS **closer** (auth, AuthZ, MCP, quotas) but **not** production multi-tenant cloud yet.

---

## Progress after upgrade (science Loop 1–2, 2026-07-18)

Research docs: [`docs/research/AGENT_MEMORY_SURVEY.md`](research/AGENT_MEMORY_SURVEY.md), [`IMPROVEMENT_PLAN.md`](research/IMPROVEMENT_PLAN.md), [`MEMORY_ARCHITECTURE_V2.md`](research/MEMORY_ARCHITECTURE_V2.md).

### Newly shipped (science-honest)

| Item | Status | Literature link (inspiration ≠ full paper claim) |
|------|--------|--------------------------------------------------|
| RIR scoring (recency × importance × relevance) | **Shipped** — `scoring.py`; wired into retrieve re-rank + pack; `CONTINUUM_DISABLE_RIR` ablation | Park et al. Generative Agents (approx. importance; not LLM 1–10 by default) |
| Memory graph 1-hop | **Shipped** — `graph.py` + `memory_edges` table; entity `related_to` + supersedes edges | HippoRAG/A-MEM *subset* only — **no** Personalized PageRank |
| Episodic→semantic consolidate | **Shipped** — heuristic distill; `POST /v1/memories/consolidate` + MCP `memory_consolidate` | Reflection stub, not full Generative Agents reflection trees |
| Embed cache | **Shipped** — content-hash cache for dense retrieve | Scale hygiene, not ANN |
| Stress evals vs true keyword-naive baseline | **Shipped** — `stress_noise_budget`, `stress_stale_leakage`; Continuum aggregate recall **0.985** vs naive **0.909** | Literature-aligned recall@budget + stale leakage |

### Verified gates

- `pytest -m "unit or api or eval"` → **44 passed**
- `python evals/run_suite.py` → **PASS** (continuum ≥ naive on recall and stale)
- Stress WINs: both stress fixtures (stale fixture: Continuum recall 1.0 / stale 0.0 vs naive 0.0 / 1.0)

### Remaining gaps (do not overclaim)

| Gap | Notes |
|-----|-------|
| `stress_noise_budget` still leaks stale `8%` under tight budget | Ranking/packing tradeoff; open |
| True BM25 / ANN vector DB | Still in-process scan + cache |
| LLM importance + sleep-time Letta compute | Not implemented |
| HippoRAG PPR multi-hop | Only 1-hop edges |
| LoCoMo / LongMemEval parity | Fixture suite only |
| Postgres multi-tenant SaaS / OAuth | Unchanged |
| Alibaba free-tier cloud | Blocked; do not claim production cloud |

**Verdict after Loop 1–2:** Scientifically **credible hackathon Memory OS** with literature-aligned scoring, consolidation stub, graph edges, and eval wins under stress — still **not** a full research reproduction of HippoRAG/MemGPT/Mem0, and **not** production multi-tenant cloud SaaS.

---

## Progress after Loop 3 (2026-07-18)

Design notes: [`docs/research/LOOP3_NOTES.md`](research/LOOP3_NOTES.md).

### Newly shipped

| Item | Status | Honesty note |
|------|--------|--------------|
| Noise-budget stale leak fix | **Shipped** — obsolescence extractor cues; supersession never installs obsolete values; packer `filter_packable` + type/slot priors; regression `test_noise_budget_stale.py` | `stress_noise_budget` Continuum `stale_leakage ≈ 0` |
| Pure-Python BM25 sparse retrieve | **Shipped** — `bm25.py` wired into `sparse_retrieve` | Okapi BM25 over workspace corpus, not Lucene |
| Numpy IVF-lite ANN | **Shipped** — `ann_index.py`; optional `faiss` if importable | Brute cosine for N≤256; not a managed vector DB |
| HippoRAG-style PPR multi-hop | **Shipped** — `personalized_pagerank` + `expand_ppr` in `graph.py` | PPR on entity/supersedes edges only — not full HippoRAG OpenIE |
| LoCoMo-*style* eval fixtures | **Shipped** — `evals/fixtures/locomo_*.json` (temporal, cross-session, adversarial stale) | Synthetic; **not** official LoCoMo dump/leaderboard |
| Multi-tenant org isolation | **Shipped** — `org_id` on store list/search/get/forget; API `_resolve_request_org`; `CONTINUUM_API_KEY_MAP` | API keys → org; not OAuth/RBAC |
| Postgres store path | **Shipped** — SQLAlchemy `PostgresMemoryStore` via `DATABASE_URL` | Optional deps; SQLite remains default |

### Migration (SQLite → Postgres)

1. `pip install sqlalchemy "psycopg[binary]"` (or `psycopg2-binary`)
2. Set `DATABASE_URL=postgresql://user:pass@host:5432/continuum`
3. First connect creates tables idempotently
4. Set `CONTINUUM_API_KEY_MAP` before enabling auth
5. Rollback: unset `DATABASE_URL`, use `CONTINUUM_DB_PATH`

### Verified gates (Loop 3)

- `pytest -m "unit or api or eval"` → **68 passed**
- `python evals/run_suite.py` → **PASS** (26 fixtures; continuum recall **1.000** / stale **0.000** vs naive **0.923** / **0.038**)
- `stress_noise_budget`: Continuum recall 1.0 / **stale 0.0** (WIN vs naive)

### Remaining gaps

| Gap | Notes |
|-----|-------|
| OAuth / full SaaS RBAC | API key → org only |
| Managed vector DB / FAISS required path | Optional; numpy IVF-lite default |
| Official LoCoMo / LongMemEval dumps | Style fixtures only |
| LLM importance + Letta sleep-time | Not implemented |
| Billing, PITR, policy engine | Not started |

**Verdict after Loop 3:** Scientifically **stronger** (BM25+ANN+PPR, stale-leak closed, LoCoMo-style evals) and SaaS **closer** (real org isolation + Postgres path) — still a hackathon-grade Memory OS, not production multi-tenant cloud.

---

## Progress after Loop 4–5 (2026-07-18)

Design notes: [`docs/research/LOOP4_NOTES.md`](research/LOOP4_NOTES.md), [`docs/research/LOOP5_NOTES.md`](research/LOOP5_NOTES.md).

### Loop 4 (shipped earlier)

LLM-optional importance, reflection-*style* consolidate summaries, policy PII/retention stubs, lexical `cite_overlap` explain, as-of LoCoMo-*style* fixtures, env-map RBAC roles.

### Loop 5 newly shipped

| Item | Status | Honesty note |
|------|--------|--------------|
| Heuristic faithfulness critic | **Shipped** — `faithfulness_score` + pack soft-demote | Not NLI/entailment |
| Adversarial injection quarantine | **Shipped** — detect/tag/exclude; turn-level inherit | Pattern quarantine — not full guardrail |
| Utility outcome writeback | **Shipped** — `record_outcome` + HTTP/OpenAI tool | Labeled deltas — not RL |
| Async sleep-time consolidate | **Shipped** — in-process job worker | Not Celery/durable queue |
| Temporal supersedes-chain expand | **Shipped** — retrieve on temporal cues | Not Graphiti temporal KG |
| OpenAI tools + SSE chat | **Shipped** — `/v1/openai/tools`, `/v1/chat/stream` | Not Chat Completions proxy |
| Console stats/graph hooks | **Shipped** — `/v1/memories/stats`, `/graph` | UI inspector helpers |

### Remaining gaps

| Gap | Notes |
|-----|-------|
| OAuth / full SaaS RBAC | Env-map roles only |
| NLI faithfulness / official LoCoMo dumps | Deferred |
| Durable sleep-time / managed vector DB | Deferred |
| Billing, PITR | Deferred |

**Verdict after Loop 5:** Scientifically **stronger** on faithfulness signals, injection hardening, outcome utility, and temporal chain retrieve; SaaS surface **wider** (OpenAI tools + SSE). Still hackathon-grade Memory OS — not production multi-tenant cloud.
