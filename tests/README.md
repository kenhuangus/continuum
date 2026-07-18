# Continuum regression tests

Reusable pytest suites for Continuum. Markers select which layer to run.

## Layout

| Path | Marker | What it covers |
|------|--------|----------------|
| `tests/unit/` | `unit` | `memory_core` store, packer, supersession |
| `tests/api/` | `api` | FastAPI `TestClient` regression (temp DB, no live server) |
| `tests/e2e/` | `e2e` | Playwright browser UI (server + Chromium) |
| `tests/conftest.py` | — | Shared fixtures (`api_client`, `e2e_server`, `base_url`, …) |

## Run

```bash
# Install dev deps (once)
pip install -e ".[dev]"

# Unit only (offline, fastest)
pytest -m unit

# API regression via TestClient (offline, temp SQLite)
pytest -m api

# Browser e2e (needs Chromium; starts uvicorn if /v1/health is down)
playwright install chromium
pytest -m e2e

# Everything collectable (e2e skips cleanly if server/browser unavailable)
pytest
```

## Environment

| Variable | Default | Purpose |
|----------|---------|---------|
| `CONTINUUM_BASE_URL` | `http://127.0.0.1:8000` | Base URL for e2e browser tests |
| `CONTINUUM_DB_PATH` | set per fixture | API tests force a temp DB before importing the app |

## Notes

- **API tests** reload `continuum_api.main` after setting `CONTINUUM_DB_PATH` so they never write to `data/continuum.db`.
- **E2E** prefers an already-running API at `CONTINUUM_BASE_URL`. If health fails and the port is free, a session-scoped uvicorn is started and torn down. If startup fails, tests `pytest.skip` with a clear message.
- Screenshots on failed e2e steps (when using the function-scoped `page` fixture) go under `test_artifacts/`.
- Offline smoke eval remains at `python evals/run_smoke.py` (not part of this pytest tree).
