# Evaluations

## Smoke eval (Phase A)

```bash
python evals/run_smoke.py
```

Uses `evals/fixtures/acme_session_a_b.json`:

1. Ingest Session A turns (VIP, 12% discount, email preference)
2. Pack for Session B query under tight budget with `type_quota`
3. Assert expected signals present without exceeding budget

Runs offline — no Qwen API key required.

## Browser UI regression

Prefer the pytest e2e suite (Playwright):

```bash
pip install -e ".[dev]"
playwright install chromium
pytest -m e2e
```

See [tests/README.md](../tests/README.md). The legacy script `evals/browser_ui_test.py` is a thin wrapper that invokes `pytest -m e2e`.

## Future

- Retrieval recall@k benchmarks
- Forgetting regression suite
- Pack efficiency metrics
