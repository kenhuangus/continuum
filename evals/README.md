# Evaluations

## Smoke eval

```bash
python evals/run_smoke.py
```

Uses `evals/fixtures/acme_session_a_b.json` (VIP / discount supersession / email). Offline — no API key.

## Full suite

```bash
python evals/run_suite.py
# or: python -m continuum_eval  (evals/ on PYTHONPATH)
pytest -m eval -q
```

Baselines per fixture: `no_memory`, `full_history_dump`, `naive_topk_keyword`, `continuum_pack`.

Metrics: critical-fact recall@budget, stale leakage after supersession, token use.

Pass criterion: aggregate Continuum recall ≥ naive and stale leakage ≤ naive.

### LoCoMo-style fixtures

`evals/fixtures/locomo_*.json` are long-context, multi-session conversational fixtures
modeled on the [LoCoMo](https://arxiv.org/abs/2402.17753) benchmark style: facts are
introduced, revised, and superseded across several turns in `session_a`, then probed
by a single `session_b` query that requires picking the *current* answer rather than
any earlier value.

- `locomo_multi_session_temporal.json` — Initech's discount is approved, then revised
  twice more (5% → 10% → 18%) alongside a VIP-status note and an account-owner update,
  interleaved across the session. Tests that only the latest discount survives
  supersession and that unrelated facts (VIP, owner) are still recalled together.
- `locomo_cross_session_entity_facts.json` — two unrelated entities (Northwind, Bramble
  Co) each get distinct fact types (VIP/discount vs. SLA/owner) plus an off-topic
  filler turn. Tests that retrieval keeps per-entity facts separate and ignores noise.
- `locomo_adversarial_stale.json` — Vertex's SLA response time is set (2 hours) after
  an explicit "obsolete"/"earlier we had floated ... 4 hours" cue, plus four
  `seed_memories` distractor documents engineered to share keywords (SLA, response,
  contact, preference) with the real facts but carry no numeric payload. Tests that
  the obsolescence-marker path (extractor → supersession → packer filter) keeps the
  stale "4 hours" out of the packed context even under keyword-similarity pressure.
- `locomo_temporal_preference_change.json` — a contact-channel preference changes
  twice (email → phone → slack) for the same entity. Tests that only the final
  preference is active/recallable and the two earlier channels are fully superseded
  (not just budget-excluded).

These fixtures run automatically as part of `python evals/run_suite.py` and
`pytest -m eval -q` alongside the rest of `evals/fixtures/*.json` — no separate
invocation is needed.

## Browser UI regression

```bash
pytest -m e2e
```

See [tests/README.md](../tests/README.md).
