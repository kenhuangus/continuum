# Proof of Alibaba Cloud Deployment (stub)

Phase A runs locally on SQLite. Production deployment targets Alibaba Cloud services:

| Service | Role | Code reference (planned) |
|---------|------|--------------------------|
| API Gateway | Public HTTPS, auth, rate limits | `infra/api-gateway/` (Phase B) |
| Function Compute / ACK | API + agent runtime | `apps/api/`, `packages/agent/` |
| Tablestore / RDS | Durable memory store | replaces `continuum_memory.store` |
| Redis | Hot cache + pack previews | `infra/redis/` |
| OSS | Artifact refs + eval artifacts | `packages/memory_core` artifact_ref type |
| ARMS / SLS | Observability | `infra/observability/` |

## Deployment checklist (Phase B+)

- [ ] Containerize API (`Dockerfile` in `apps/api/`)
- [ ] Push image to ACR
- [ ] Provision Tablestore instance + schema migration from SQLite
- [ ] Configure API Gateway → FC/ACK routing
- [ ] Set `DASHSCOPE_API_KEY` in KMS / env
- [ ] Run smoke eval against staging endpoint

## Qwen Cloud

Model calls use DashScope compatible mode:

`https://dashscope-intl.aliyuncs.com/compatible-mode/v1`

See `.env.example` and `continuum_agent.client.QwenClient`.
