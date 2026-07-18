# Alibaba Cloud Deployment Plan (stub)

## Target topology

```
Internet → API Gateway → ACK/FC (Continuum API) → Tablestore
                              ↓
                         DashScope (Qwen)
                              ↓
                         Redis (pack cache)
```

## Phase A (local)

- SQLite at `data/continuum.db`
- `uvicorn continuum_api.main:app --reload --host 127.0.0.1 --port 8000`

## Phase B tasks

1. **Container** — Dockerfile for `continuum_api`
2. **ACR** — push image
3. **ACK** — Deployment + Service + Ingress (or FC HTTP trigger)
4. **Tablestore** — migrate schema from SQLite ADR
5. **Secrets** — KMS for `DASHSCOPE_API_KEY`
6. **CI** — pytest + smoke eval on PR

See [docs/PROOF_OF_ALIBABA_DEPLOYMENT.md](../docs/PROOF_OF_ALIBABA_DEPLOYMENT.md).
