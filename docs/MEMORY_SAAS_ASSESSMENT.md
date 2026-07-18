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
