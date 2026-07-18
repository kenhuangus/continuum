# Loop 5 — Research → Design Notes

**Date:** 2026-07-18  
**Base:** Loop 4 commit `8770a4f` (+ parallel UI stats/graph hooks on working tree)  
**Honesty bar:** Inspiration ≠ paper reproduction; document limits. No Alibaba deploy. No secrets.

---

## Step A baseline (pre-Loop 5)

| Gate | Expected at L4 |
|------|----------------|
| `pytest -m "unit or api or eval" -q` | Green (~68+ unit/api/eval) |
| `python evals/run_suite.py` | PASS; Continuum ≥ naive on recall/stale |
| Latest master | Includes Loop 4 + demo video pipeline (`831ddc7`) |

---

## Remaining high-impact gaps after Loop 4

| Gap | Status at L4 | Loop 5 stance |
|-----|--------------|---------------|
| Packer faithfulness beyond lexical Jaccard | `cite_overlap` only | **Ship** heuristic faithfulness critic (entity coverage + contradiction cues) |
| NLI entailment faithfulness | None | Defer (research-grade ocean) |
| Adversarial memory injection | Basic pack sanitize in agent | **Ship** write-time detect + pack quarantine + eval fixture |
| Utility learning from outcomes | +0.02 pack-access bump only | **Ship** explicit outcome writeback API |
| Sleep-time / async consolidate | Sync `POST /consolidate` only | **Ship** in-process async worker stub (not Celery) |
| Graph multi-hop temporal | PPR + 1-hop; as-of list filter | **Ship** supersedes-chain expand on temporal queries |
| Eval diversity (injection / outcome) | LoCoMo-style + as-of | **Ship** adversarial injection + outcome-utility fixtures |
| Streaming UX hooks | Sync `/v1/chat` only | **Ship** SSE `/v1/chat/stream` |
| OpenAI-compatible memory tools surface | MCP + REST only | **Ship** `/v1/openai/tools` (+ call dispatcher) |
| Official LoCoMo / LongMemEval dumps | Synthetic only | Defer |
| Managed vector DB / OAuth / billing | Partial / stubs | Defer |

---

## Chosen P0s (5 concrete, one loop)

### L5.1 — Heuristic faithfulness critic (beyond lexical overlap)

**Inspiration:** RAG faithfulness / citation grounding (approx.); not NLI models.

**Design:**
- Extend `explain.py` with `faithfulness_score(query, content, *, entities=None) -> dict`:
  - `cite_overlap` (existing Jaccard)
  - `entity_coverage`: fraction of query CapWords / memory entities present in content
  - `contradiction_penalty`: cue match (`not`, `never`, `obsolete`, `ignore previous`, opposing numbers vs query digits)
  - `score = clip(0.5*overlap + 0.4*entity_coverage - contradiction_penalty)`
- Attach `faithfulness` into `explanation_details`.
- Pack soft-demote: when query non-empty, subtract `(1 - faithfulness.score) * 0.3` from pack `_score` (env `CONTINUUM_DISABLE_FAITHFULNESS=1` ablation).

**Honest claim:** Heuristic grounding score — **not** NLI/entailment faithfulness.

### L5.2 — Adversarial memory injection defenses

**Inspiration:** Prompt-injection via retrieved docs; PRD E8.

**Design:**
- New `injection.py`: `detect_injection(content) -> list[str]` patterns (ignore prior instructions, system role spoof, tool exfil, jailbreak cues).
- On write (`apply_policy_on_write` or remember path): merge `policy_tags += ["injection_risk"]` (+ optional `untrusted`).
- On pack: if `injection_risk` present, either exclude (`CONTINUUM_PACK_EXCLUDE_INJECTION=1`, default **on**) or sanitize content in-place for packing only.
- Strengthen shared sanitize used by agent + packer path.
- Fixture `evals/fixtures/adversarial_injection.json`: poisoned memory must not win pack / must not appear as instruction payload; critical facts still recalled.
- Unit + eval coverage.

**Honest claim:** Pattern + tag quarantine — **not** a full LLM guardrail product.

### L5.3 — Utility learning from outcomes

**Inspiration:** Reflexion / writeback; PRD M10.

**Design:**
- `MemoryService.record_outcome(workspace_id, memory_ids, success: bool, *, note=None, org_id=...)`:
  - success → `utility = min(2.0, utility + 0.15)`
  - failure → `utility = max(0.1, utility - 0.2)`; tag `outcome:fail`
  - Optional: on failure write a short `procedural` episodic note (heuristic) when `note` provided.
- HTTP `POST /v1/memories/outcome` (writer/admin).
- MCP tool `memory_outcome` (optional if time).
- Unit tests for delta bounds; eval fixture soft-check that high-utility winners pack preferentially after success labeling.

**Honest claim:** Explicit labeled writeback — **not** offline RL or causal credit assignment.

### L5.4 — Sleep-time async consolidate worker

**Inspiration:** Letta sleep-time compute.

**Design:**
- `sleep_worker.py`: in-process `threading` worker + job dict (`pending|running|done|error`).
- `POST /v1/memories/consolidate/async` → `{job_id, status}`; runs `consolidate_workspace` off-request.
- `GET /v1/memories/consolidate/jobs/{job_id}` → status + written count.
- Env `CONTINUUM_SLEEP_WORKER=0` disables (sync-only); default enabled for API process.

**Honest claim:** In-process thread stub — **not** durable queue / multi-replica sleep-time.

### L5.5 — Temporal supersedes-chain expand

**Inspiration:** Graphiti bi-temporal / HippoRAG multi-hop along conflict edges.

**Design:**
- In `retrieve.py` / `graph.py`: when query matches temporal cues (`before`, `after`, `previously`, `at the time`, `as of`, `was`), expand along `supersedes` / `superseded_by` chains (depth ≤ 3) and merge into candidates before RIR.
- Prefer chain neighbors that fall inside `as_of` when set.
- Fixture / unit: multi-version discount facts; temporal query surfaces correct generation.

**Honest claim:** Supersedes-chain walk — **not** full temporal KG reasoning.

### L5.6 — OpenAI-compatible tools + streaming chat hooks

**Design:**
- `GET /v1/openai/tools` → OpenAI function/tool JSON schemas for search/remember/forget/list/pack/explain/consolidate/outcome.
- `POST /v1/openai/tools/call` `{name, arguments}` → dispatch (auth + RBAC).
- `POST /v1/chat/stream` → SSE events: `pack`, `reply`, `written`, `done` (and `error`).
- Preserve existing sync `/v1/chat`; do not break web console stats/graph endpoints from parallel work.

**Honest claim:** Schema-compatible tool surface + SSE — **not** full Chat Completions proxy.

---

## Explicitly deferred

- Official LoCoMo / LongMemEval ingestion  
- Cross-encoder / NLI faithfulness  
- Celery/RQ/Redis sleep-time  
- OAuth2 / billing / PITR  
- Alibaba cloud deploy  

---

## Done criteria

1. `pytest -m "unit or api or eval" -q` green  
2. `python evals/run_suite.py` PASS; Continuum ≥ naive on recall/stale  
3. Tests for: faithfulness score, injection quarantine, outcome utility, async consolidate job, temporal chain, openai tools / stream smoke  
4. `docs/research/LOOP5_NOTES.md` + assessment progress blurb; science-honest claims; no secrets  
5. Commit + push to `kenhuangus/continuum`
