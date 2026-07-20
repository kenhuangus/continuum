# Free hosting options for Continuum (non-Alibaba + leftovers)

**Date:** 2026-07-20  
**App:** Continuum MemoryAgent — FastAPI + static web UI + SQLite (Docker on port **8000**)  
**Repo:** https://github.com/kenhuangus/continuum  
**Context:** Six Alibaba free ECS attempts failed overnight; no `PUBLIC_URL`. This doc answers: *can we put Continuum on other free hosting for a Devpost “Try it” link?*

## Honest Alibaba note

**Hosting Continuum elsewhere does not satisfy “proof of Alibaba Cloud deployment.”**  
Judges still want Alibaba compute evidence if that is a Track 1 PoD requirement. A Render/Railway/HF URL is only a **fallback demo URL** while Alibaba compute is blocked. Keep Alibaba screenshots + `docs/PROOF_OF_ALIBABA_DEPLOYMENT.md` honest (not live).

---

## How Continuum is meant to be deployed

| Item | Value |
|------|--------|
| Container | Root [`Dockerfile`](../Dockerfile) — `python:3.12-slim`, `pip install -e .` |
| Process | `uvicorn continuum_api.main:app --host 0.0.0.0 --port 8000` |
| Compose | [`docker-compose.yml`](../docker-compose.yml) — volume `continuum-data` → `/app/data` |
| Health | `GET /v1/health` → `{"status":"ok","service":"continuum",...}` |
| UI | Static files from `apps/web` served by the same FastAPI process |
| Default DB | **SQLite** at `CONTINUUM_DB_PATH` (Docker default `/app/data/continuum.db`) |
| Postgres | Optional via `DATABASE_URL=postgresql://...` (not required for demo) |
| Auth | `CONTINUUM_AUTH_DISABLED=1` for open demo; or `CONTINUUM_API_KEYS` |
| LLM | `DASHSCOPE_API_KEY` / `QWEN_API_KEY` (live Qwen); app boots without key but chat/embed degrade |
| CORS | `CONTINUUM_CORS_ORIGINS` for public origin |
| Alibaba primary | ECS + Docker (`infra/ecs/DEPLOY.md`) |
| Alibaba alt | Function Compute custom container (`infra/fc/`) — SQLite/ephemeral caveats |

**Not a fit for classic serverless JS hosts** (Vercel/Netlify functions): long-running ASGI + local SQLite file + single-process UI.

---

## Recommendation ranked (for a free public URL)

| Rank | Option | Feasibility | Free limits (approx.) | Signup friction | Alibaba proof? | Deploy complexity | Est. human time |
|------|--------|-------------|----------------------|-----------------|----------------|-------------------|-----------------|
| **1** | **Render free Web Service** | **Yes** | Free instance ~512 MB / 0.1 CPU; **spins down ~15 min idle**; ~1 min cold start; monthly free hours/bandwidth caps | **No credit card** (per Render docs) | **No** | Low — link GitHub, Docker, env vars, health `/v1/health` | **15–30 min** |
| **2** | **Railway trial** | **Maybe** | Trial credits (~$5); not permanent free | Often **card for trial** | **No** | Low — GitHub + Dockerfile | 20–40 min |
| **3** | **Google Cloud Run** | **Maybe** | Always Free quotas (reqs / vCPU-s / GiB-s) if under caps | **Billing account + card required** even for free tier | **No** | Medium — enable API, build/push image, set env, allow unauth | 30–60 min |
| **4** | **Oracle Cloud Always Free** | **Maybe** | Generous ARM/AMD VM forever-free (quota/region dependent) | Account + **card** + approval delays | **No** | Medium–high — VM + Docker + SG like ECS | 1–3 h (+ wait) |
| **5** | **Fly.io** | **Weak** | Permanent free tier **removed**; short trial (hours/days) then card | Trial may start without card; **card to stay up** | **No** | Medium — `flyctl` + Dockerfile | 20–40 min (then dies) |
| **6** | **Hugging Face Spaces (Docker)** | **Weak (2026)** | CPU Basic marketed free, but **Docker/Gradio on free CPU often requires PRO** (forum reports Jul 2026) | HF account; Pro paywall possible | **No** | Low if free Docker works | 20–40 min or blocked |
| **7** | **Azure Container Apps / App Service free** | **Maybe** | Limited free/F1; Container Apps usually needs subscription | **Card** | **No** | Medium | 45–90 min |
| **8** | **Vercel / Netlify** | **No** | N/A for this shape | — | **No** | — | — |
| **9** | **GitHub Codespaces / Gitpod** | **No for judges** | Temporary IDE URLs; sleep; not a stable Try-it | GitHub login | **No** | Low | — |

### Top pick

**Render free Web Service** is the best *realistic* free public URL for Continuum right now: Docker-native, no card, HTTPS URL, health check path supported. Expect cold starts after idle. SQLite on free tier has **no persistent disk** — memory resets on restart/spin-down (fine for a hackathon demo if you re-seed or accept ephemeral memory).

---

## Session attempt log (2026-07-20) — deploy **not** completed

| Check | Result |
|-------|--------|
| Docker Desktop engine | **Not running** (cannot local build/push) |
| `DASHSCOPE_API_KEY` in repo `.env` | **Missing** (only Alibaba RAM keys present) |
| Render / Railway / Fly tokens/CLIs | **Missing** |
| `gcloud` | Logged in; **0 billing accounts** → Cloud Run free tier **blocked** without human billing link |
| `HF_TOKEN` | Valid as `kenhuangus`, but token role **`read` only**; `isPro=false`; create Space → **403** |
| `aliyun` FC (`default`) | `ListFunctions` → **[]** (API works; nothing deployed) |
| SAE | **Not activated** on this profile |
| **PUBLIC_URL from this session** | **NONE** |

No paid SKU was purchased. No secrets were committed.

---

## Render deploy checklist (human, ~20 min)

1. Sign up at [render.com](https://render.com) (GitHub OAuth OK; no card for free).
2. **New → Web Service** → connect `kenhuangus/continuum`.
3. Runtime: **Docker** (root `Dockerfile`).
4. Instance: **Free**.
5. Health check path: `/v1/health`.
6. Env vars (dashboard secrets — do not commit):
   - `CONTINUUM_AUTH_DISABLED=1`
   - `CONTINUUM_DB_PATH=/app/data/continuum.db`
   - `DASHSCOPE_API_KEY=<from DashScope console>`
   - `CONTINUUM_CORS_ORIGINS=https://<your-service>.onrender.com`
7. Deploy → wait for green → open `https://….onrender.com/` and `/v1/health`.
8. Paste that URL into Devpost **Try it** as a **non-Alibaba** demo link; keep Alibaba PoD fields honest.

Optional: add a `render.yaml` Blueprint later (not required for first URL).

---

## Alibaba free paths still left (brief — not ECS)

| Path | Status / note |
|------|----------------|
| **ECS free trial / Personal Trial** | Overnight: redirects to **paid** Custom Launch; no free VM on account |
| **Function Compute free CU** | CLI lists **0** functions; custom-container possible via `infra/fc/` + ACR; SQLite poor fit; abort if billed beyond free CU |
| **SAE** | Not activated on `default` profile — human activate + confirm free offer before create |
| **SWAS / Simple Application Server** | Overnight: 0 servers; create looked like purchase |
| **ACR** | Registry only — still need somewhere to *run* the image |

Preferred Alibaba order if human can claim free compute: **free ECS > FC free CU (demo only) > paid (abort)**.

---

## What still needs a human

1. **Choose fallback:** Render free (recommended) *or* keep waiting on Alibaba free ECS.
2. **DashScope key** in host secrets (not in git) so chat works for judges.
3. **Render (or similar) signup + one-click deploy** — no API token available in this agent session.
4. **Alibaba proof** (if still required): claim free ECS / activate FC free path on the **Chrome main account**, deploy Docker, screenshot Workbench, set `PUBLIC_URL`.
5. **Devpost:** YouTube upload + Submit; if using Render URL, label it as live demo host, **not** Alibaba hosting proof.
6. Optional: upgrade HF token to **write** + Pro *only if* you want Spaces — not recommended vs Render right now.

---

## Related docs

- [OVERNIGHT_STATUS.md](OVERNIGHT_STATUS.md) — Alibaba overnight failures  
- [PROOF_OF_ALIBABA_DEPLOYMENT.md](PROOF_OF_ALIBABA_DEPLOYMENT.md) — Alibaba PoD (honest)  
- [DEVPOST_SUBMIT_PACKET.md](DEVPOST_SUBMIT_PACKET.md) — paste-ready fields  
- [../infra/README.md](../infra/README.md) — Alibaba deploy guide  
