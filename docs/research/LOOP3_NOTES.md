# Loop 3 — Research → Design Notes

**Date:** 2026-07-18  
**Scope:** Close remaining Continuum science/SaaS gaps after commit `3ff2af7`  
**Honesty bar:** Inspiration ≠ full paper reproduction; document limits.

---

## 1. Noise-budget stale leak (`stress_noise_budget`)

### Root cause (code-backed hypothesis)

Fixture turn order:

1. Approve **15%** Globex discount → decision with `discount_pct=15`
2. VIP / email prefs
3. “Earlier we floated **8%** … that is **obsolete**”

`apply_supersession` treats the newer extract as winner: if turn 3 yields an active decision with `discount_pct=8`, it **supersedes the 15% memory**. Under a 60-token budget, packer type quotas then prefer “decision” content that still contains `8%` → `stale_leakage > 0`.

Also: keyword-heavy seed noise shares entities with the query; without strong type/slot priors, decisions can lose slots to noise under tight budgets.

### Design

| Layer | Change |
|-------|--------|
| Extractor | Detect obsolescence/negation cues (`obsolete`, `outdated`, `no longer`, `superseded`, `was floated`). Do **not** write obsolete numeric facts as active decisions. Optionally emit a policy tag / forget-intent for the stale value. |
| Supersession | If new text marks value V obsolete for entity E + slot K, supersede actives with `slots[K]==V`; never install V as the winning active fact. Prefer installing/retaining the conflicting *current* value when present. |
| Packer | Hard exclude `status != ACTIVE` (already via retrieve). Add **slot-winner prior**: among same entity+slot, prefer higher importance/recency and memories that *do not* carry obsolescence language. Boost `DECISION`/`PREFERENCE` over episodic noise under tight budgets. Soft-penalize content that only mentions a superseded value. |
| Eval | Dedicated regression: `stress_noise_budget` must have Continuum `stale_leakage ≈ 0` (≤ 1e-9). Unit test asserting superseded decisions cannot pack-win. |

---

## 2. BM25 / ANN / HippoRAG-style retrieval

### BM25 (sparse)

- Pure-Python Okapi BM25 over workspace memory tokens (content + entities).
- File: `packages/memory_core/continuum_memory/bm25.py`
- Wire into `sparse_retrieve` as primary scorer (keep entity/slot bonuses additive).
- No mandatory new dependency.

### ANN / dense index

- Default: **numpy IVF-lite** — random projection or coarse k-means centroids + scan shortlist; fallback to brute cosine when N small (`N ≤ 256`).
- File: `packages/memory_core/continuum_memory/ann_index.py`
- Optional extra: if `faiss` importable, use `IndexFlatIP` / IVF; document in README as optional.
- Wire into `dense_retrieve_with_sims` via shortlist then exact cosine on shortlist.

### HippoRAG-inspired multi-hop

- Extend `graph.py`: `personalized_pagerank(seed_ids, damping=0.85, iters=20)` over undirected `memory_edges`.
- `expand_ppr(...)` returns top ACTIVE nodes by PPR mass (exclude seeds).
- `retrieve_candidates`: after 1-hop, merge PPR expansion (cap ~20); re-rank with RIR.
- Honest claim: **PPR on entity/supersedes edges**, not full HippoRAG passage-graph + OpenIE pipeline.

---

## 3. LoCoMo-style evals

- Add fixtures under `evals/fixtures/locomo_*.json` (3–5):
  - Multi-session temporal (“what changed between session 1 and 3?”)
  - Cross-session entity facts
  - Adversarial stale (old % / old channel vs current)
- Metrics already in suite: `recall`, `stale_leakage`, tokens; no new metric required unless helpful (`temporal_consistency` optional soft).
- Docs: **LoCoMo-*style*** synthetic tasks — not the official LoCoMo dump / leaderboard.

---

## 4. Multi-tenant SaaS store

### Isolation

- Every read/write/forget/search/list takes `org_id` (or resolves from API key).
- SQLite queries: `WHERE org_id = ? AND workspace_id = ?`.
- Cross-org IDOR → not found (404).

### Store abstraction

- Keep `MemoryStoreProtocol` + `create_store()`.
- SQLite (`MemoryStore`) remains default.
- **Postgres path:** real SQLAlchemy implementation in `store_postgres.py` when `DATABASE_URL` is `postgres://` / `postgresql://` — same schema (memories, audit_log, memory_edges, embed_cache).
- Migration notes: `docs/research/LOOP3_NOTES.md` §Migration + `MEMORY_SAAS_ASSESSMENT.md`.

### API keys → org

- `CONTINUUM_API_KEYS=key1,key2` → all keys map to `org_demo` (compat).
- `CONTINUUM_API_KEY_MAP={"key_a":"org_a","key_b":"org_b"}` JSON preferred.
- Middleware attaches `request.state.org_id`; mutating endpoints reject body `org_id` mismatch with key’s org (403).
- Demo mode (`CONTINUUM_AUTH_DISABLED` / no keys): allow explicit `org_id` as today.

---

## 5. Done criteria

1. `pytest -m "unit or api or eval" -q` green  
2. `python evals/run_suite.py` PASS; Continuum ≥ naive aggregate  
3. `stress_noise_budget` Continuum `stale_leakage ≈ 0`  
4. Unit tests: BM25, ANN shortlist, PPR expansion, org isolation, API key→org  
5. Docs updated; no secrets pushed  

---

## Migration notes (SQLite → Postgres)

1. Set `DATABASE_URL=postgresql://user:pass@host:5432/continuum`.
2. Install optional deps: `pip install sqlalchemy psycopg[binary]` (or `psycopg2-binary`).
3. First connect creates tables (idempotent `CREATE TABLE IF NOT EXISTS`).
4. Export SQLite → import: dump memories/edges/audit as JSON or use a one-shot script; Phase A DBs are small — offline export via `store.list_by_workspace` per org is acceptable.
5. Set `CONTINUUM_API_KEY_MAP` for tenant keys before enabling auth.
6. Rollback: unset `DATABASE_URL`, point `CONTINUUM_DB_PATH` at SQLite file.
