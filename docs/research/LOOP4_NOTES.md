# Loop 4 — Research → Design Notes

**Date:** 2026-07-18  
**Base:** Loop 3 commit `b5c1baa`  
**Honesty bar:** Inspiration ≠ paper reproduction; document limits. No Alibaba deploy work.

---

## Step A baseline (pre-Loop 4)

| Gate | Result |
|------|--------|
| `pytest -m "unit or api or eval" -q` | **68 passed**, 19 deselected |
| `python evals/run_suite.py` | **PASS** (continuum recall=1.0, stale=0.0 aggregate) |
| `python evals/run_smoke.py` | **PASS** |
| Uncommitted tracked fixes | **None** (clean tree at `b5c1baa`) |

---

## Remaining gaps after Loop 3

| Gap | Status at L3 | Loop 4 stance |
|-----|--------------|---------------|
| LLM importance / Letta sleep-time | Heuristic I only; consolidate `client=` unused | **Ship** optional LLM importance + LLM consolidate summaries |
| Official LoCoMo dump / leaderboard | Synthetic LoCoMo-*style* only | **Not** this loop — stay synthetic; add **as-of** PIT fixtures |
| Managed vector DB | Local ANN + optional FAISS | Defer managed; skip hnswlib (low ROI at eval N) |
| OAuth / full RBAC | API key → org map | **Ship** lightweight roles (reader/writer/admin) via env map |
| Billing / PITR | Out of scope for OSS core | Defer |
| Policy / PII retention | `policy_tags` storage only | **Ship** stub engine: detect/tag/filter/expire |
| Pack explain faithfulness | String rationales only | **Ship** structured cite + overlap score + HTTP explain |
| Faithfulness NLI critic | None | Defer (research-grade ocean) |

---

## Chosen P0s (3–5 concrete, one loop)

### L4.1 — LLM-optional importance scoring

**Inspiration:** Generative Agents importance rating (Park et al.); Continuum docs already gate claim on `CONTINUUM_LLM_IMPORTANCE`.

**Design:**
- Add `score_importance_with_llm(content, client) -> float | None` in `scoring.py`.
- When `CONTINUUM_LLM_IMPORTANCE=1` **and** `client` present: ask for 1–10 importance JSON; normalize to [0,1]; set `Memory.importance`.
- On failure / no client / flag off: keep heuristic `importance_score` (no regression).
- Wire in `MemoryService.ingest_turn` / `remember` path after extract.
- Unit tests with fake client; live LLM skipped in CI.

**Honest claim:** Optional LLM importance blend — **not** Generative Agents full reflection tree.

### L4.2 — Sleep-time / reflection consolidate improvements

**Inspiration:** Letta sleep-time compute; Generative Agents reflection.

**Design:**
- Use `client` in `consolidate_workspace` when present: LLM summary of group contents; fallback to `"Distilled: …"` join.
- Tag distilled with `policy_tags=["distilled","reflection"]` when LLM path used; sources still get `consolidated`.
- Prefer higher-importance episodics in group ordering (top 5 by `importance_score`).
- Still **sync** job via existing `POST /v1/memories/consolidate` — **not** an async sleep-time queue.

**Honest claim:** Reflection-*style* consolidate stub with optional LLM summary.

### L4.3 — Policy engine stubs (PII / retention)

**Design (new `policy.py`):**
- `detect_policy_tags(content) -> list[str]`: email/phone/SSN-ish heuristics → `pii`; optional `retention:short` if tagged.
- `apply_policy_on_write(memory)`: merge detected tags; if `retention:short` and no `effective_to`, set TTL (default 7 days).
- `filter_by_policy(memories, *, exclude_tags=...)`: drop memories with excluded tags (default pack excludes nothing unless `CONTINUUM_PACK_EXCLUDE_PII=1`).
- Wire write-time in service ingest/remember; pack/retrieve honor exclude when env set.
- Forgetting pass already honors `effective_to` — retention tags piggyback.

**Honest claim:** Heuristic policy stubs — **not** GDPR/DSAR product compliance.

### L4.4 — Packer faithfulness / explain improvements

**Design:**
- Extend `PackedContext` with optional `explanation_details: list[dict]` (id, included, score breakdown, cite_overlap).
- `cite_overlap(query, content) -> float`: token Jaccard / sparse overlap for faithfulness signal.
- `explain_pack_structured(...)` in `explain.py`.
- HTTP `GET /v1/memories/explain?memory_id=&workspace_id=&query=` returning structured JSON (MCP already has string explain).

**Honest claim:** Lexical cite-overlap — **not** NLI/entailment faithfulness.

### L4.5 — Temporal as-of LoCoMo-style tasks

**Design:**
- Extend `_seed_memories` to accept `effective_from` / `effective_to` / `importance` / `policy_tags`.
- Eval baselines pass `as_of` from fixture `session_b.as_of` (ISO) into `list_memories` / `pack`.
- New fixtures: `locomo_as_of_point_in_time.json` (what was true at T1 vs T2 windows).
- Docs: still **LoCoMo-style synthetic** — not official dump.

### L4.6 — Lightweight RBAC (bonus if time)

**Design:**
- `CONTINUUM_API_KEY_ROLES='{"key":{"org":"org_a","role":"reader"}}'`
- Roles: `reader` (GET/search/pack/explain), `writer` (+ remember/chat/consolidate), `admin` (+ forget/forgetting pass).
- Middleware sets `request.state.role`; mutating routes check role → 403.
- Unmapped keys default `writer` (compat with Loop 3).
+ Keys only in `CONTINUUM_API_KEYS` / `KEY_MAP` default **admin** (preserves Loop 3 forget). Keys in `ROLES` use the listed role.

---

## Explicitly deferred

- Official LoCoMo leaderboard ingestion  
- Managed vector DB / hnswlib  
- OAuth2 / OIDC  
- Billing, PITR, multi-region  
- Async sleep-time worker queue  
- NLI faithfulness critic  

---

## Done criteria

1. `pytest -m "unit or api or eval" -q` green  
2. `python evals/run_suite.py` PASS; Continuum ≥ naive  
3. Unit/API tests for: LLM importance fake-client, consolidate LLM path, policy tags, structured explain, as_of fixture, RBAC roles  
4. Docs updated; science-honest claims; no secrets in git  
5. Push to `kenhuangus/continuum`
