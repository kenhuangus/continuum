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

## Browser UI regression

```bash
pytest -m e2e
```

See [tests/README.md](../tests/README.md).
