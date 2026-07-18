# ECS Security Group (Continuum)

Create a security group in the same VPC/region as your ECS instance.

## Inbound rules

| Protocol | Port | Source | Purpose |
|----------|------|--------|---------|
| TCP | 22 | Your IP /32 (or bastion) | SSH administration |
| TCP | 8000 | 0.0.0.0/0 (or restrict to judges/your IP) | Continuum API + demo UI |

For hackathon demos, public `8000` is typical. Tighten to your IP during setup, then open for judges if needed.

## Outbound rules

| Protocol | Port | Destination | Purpose |
|----------|------|-------------|---------|
| All | All | 0.0.0.0/0 | DashScope API, Docker pulls, apt updates |

Continuum calls Qwen via DashScope at `https://dashscope-intl.aliyuncs.com` (HTTPS outbound).

## Notes

- Do **not** store `DASHSCOPE_API_KEY` in this repo; use `/etc/continuum.env` on the instance.
- Prefer assigning an **Elastic IP** so the public URL stays stable through judging.
- Optional: put HTTPS in front (SLB + cert) in Phase B; HTTP on `:8000` is enough for MVP PoD.
