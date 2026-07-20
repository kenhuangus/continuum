# Devpost Submit Packet — Continuum (MemoryAgent)

Hackathon: [Global AI Hackathon Series with Qwen Cloud](https://qwencloud-hackathon.devpost.com/)  
Deadline: **July 20, 2026 @ 2:00pm PDT**

---

## YOU MUST DO (human-only)

1. **YouTube:** Upload `demo_video/continuum_demo.mp4` (public or unlisted) → copy URL. (Login required — agent cannot do this.)
2. **Optional but strongly recommended for eligibility:** Claim a **free** Alibaba ECS (or free FC sandbox), deploy Continuum, verify `http://PUBLIC_IP:8000/v1/health`, capture Workbench **Running** screenshot → replace `docs/screenshots/alibaba_workbench.png` and update PUBLIC_URL in proof doc / this packet.
3. **Devpost:** Create/edit project → paste fields below → upload `docs/architecture.png` + Workbench PNG → paste YouTube URL + repo URL → **click Submit** (CAPTCHA/SMS if prompted).
4. **Do not** buy paid ECS SKUs for this path.

Everything else below is ready to copy-paste.

---

## Project identity

| Field | Paste this |
|-------|------------|
| **Project title** | Continuum |
| **Tagline** | Memory Operating System for agents — accumulate, retrieve, pack under budget, forget on purpose, cite memory IDs. |
| **Track** | **MemoryAgent** |
| **Built during** | Submission period (Track 1 MemoryAgent vertical slice on Qwen Cloud + Alibaba Cloud) |

---

## Exact URLs

| Asset | URL / path |
|-------|------------|
| **Public repo** | https://github.com/kenhuangus/continuum |
| **LICENSE** | Apache-2.0 (repo root) |
| **Architecture PNG (raw)** | https://raw.githubusercontent.com/kenhuangus/continuum/master/docs/architecture.png |
| **Architecture page** | https://github.com/kenhuangus/continuum/blob/master/docs/architecture.md |
| **Qwen / DashScope code proof** | https://github.com/kenhuangus/continuum/blob/master/packages/agent/continuum_agent/client.py |
| **Proof of deployment doc** | https://github.com/kenhuangus/continuum/blob/master/docs/PROOF_OF_ALIBABA_DEPLOYMENT.md |
| **Overnight status** | https://github.com/kenhuangus/continuum/blob/master/docs/OVERNIGHT_STATUS.md |
| **Workbench screenshot (local path)** | `docs/screenshots/alibaba_workbench.png` — **refresh after free reclaim** (current file is stale; see overnight shots) |
| **Demo video (local)** | `demo_video/continuum_demo.mp4` (~3:37) |
| **PUBLIC_URL (test link)** | **https://continuum-8hwx.onrender.com/** (Render free — **not** Alibaba PoD). Health: https://continuum-8hwx.onrender.com/v1/health |
| **Alibaba PUBLIC_URL** | **NONE** — overnight: prior ECS gone; Trial Center → paid; no free compute (see OVERNIGHT_STATUS / RENDER_DEVPOST_STATUS) |
| **YouTube** | **YOU PASTE AFTER UPLOAD** (or attach `demo_video/continuum_demo.mp4` if Devpost allows file upload) |

---

## Built With

- Qwen Cloud
- Alibaba Cloud
- DashScope (OpenAI-compatible API)
- Python
- FastAPI
- SQLite
- Docker
- MCP (Model Context Protocol)
- Uvicorn

---

## Full description (English) — paste into Devpost

**Continuum** is a Track 1 **MemoryAgent** — a production-minded Memory Operating System for agents.

Agents forget. Continuum makes memory first-class: it **accumulates** typed memories across sessions, **hybrid-retrieves** candidates, **packs** only what fits a strict token budget, **forgets** stale or superseded facts on purpose, and **cites memory IDs** so answers are auditable.

### What it does

- **Session A → Session B:** preferences and decisions survive as structured memories, not raw chat dumps.
- **Hybrid retrieve + context packer:** dense/sparse-style retrieval then knapsack-style packing under a budget.
- **Forgetting / supersession:** outdated facts can be retired without poisoning later answers.
- **Demo UI + REST API:** FastAPI (`/v1/chat`, `/v1/memories`, pack preview, forget) plus a browser demo.
- **MCP server:** memory tools for MCP-capable clients.
- **Qwen Cloud:** reasoning and extraction via DashScope International compatible-mode (`https://dashscope-intl.aliyuncs.com/compatible-mode/v1`) in `continuum_agent.client.QwenClient`.

### Alibaba Cloud

Deployment target is **Alibaba Cloud** (ECS + Docker primary; Function Compute scaffolding included). Containerization and runbooks live under `infra/`. Overnight: prior free Singapore ECS was gone; Trial Center redirected to paid Custom Launch; free claim needs human Start for Free; **no free running compute** — paid paths aborted. Honest proof: `docs/PROOF_OF_ALIBABA_DEPLOYMENT.md`, `docs/OVERNIGHT_STATUS.md`.

### Live demo (Render — not Alibaba proof)

Judges can try the app at **https://continuum-8hwx.onrender.com/** (free Render Docker). Health: `/v1/health`. This is a **fallback Try-it URL**, not proof of Alibaba deployment. `DASHSCOPE_API_KEY` may be unset (chat can degrade); auth disabled for demo.

### Why it fits MemoryAgent

The track asks for efficient storage/retrieval, timely forgetting, and critical recall under limited context. Continuum makes those three requirements the product core, with open-source Apache-2.0 code judges can run locally (`uvicorn continuum_api.main:app`) and evaluate via `evals/`.

### Testing instructions

1. Clone https://github.com/kenhuangus/continuum  
2. `pip install -e ".[dev]"` · copy `.env.example` → `.env` · set `DASHSCOPE_API_KEY` · `CONTINUUM_AUTH_DISABLED=1`  
3. `uvicorn continuum_api.main:app --host 127.0.0.1 --port 8000` → open http://127.0.0.1:8000/  
4. If live deploy exists: open `PUBLIC_URL` and `PUBLIC_URL/v1/health` (expect `status: ok`).  
5. Architecture diagram: `docs/architecture.png`.

---

## Devpost form field mapping

| Devpost field | Use |
|---------------|-----|
| Project name | Continuum |
| Tagline | Memory Operating System for agents — accumulate, retrieve, pack under budget, forget on purpose, cite memory IDs. |
| Track / category | MemoryAgent |
| GitHub repo URL | https://github.com/kenhuangus/continuum |
| Proof of deployment — code file | https://github.com/kenhuangus/continuum/blob/master/packages/agent/continuum_agent/client.py |
| Proof of deployment — screenshot | Upload `docs/screenshots/alibaba_workbench.png` (refresh after live free deploy) |
| Architecture image | Upload `docs/architecture.png` (or raw GitHub URL above) |
| Demo video URL | YouTube URL after you upload `demo_video/continuum_demo.mp4` |
| Description | Full description section above |
| Built With | List above — **must include Qwen Cloud** |
| Demo / test link | https://continuum-8hwx.onrender.com/ (Render; label as non-Alibaba demo) |
| Additional info | Link overnight status + proof docs if judges need honesty on deploy timing |

---

## YouTube upload instructions (human)

1. Open YouTube Studio (logged-in Google account).  
2. Upload `C:\Users\kenhu\qwen-hacktoh\demo_video\continuum_demo.mp4`.  
3. Title: `Continuum — MemoryAgent demo (Qwen Cloud Hackathon)`.  
4. Visibility: **Public** or **Unlisted** (judges must open without login walls).  
5. Wait for processing → copy share URL → paste into Devpost.  
6. Optional: trim to ≤3:00 in YouTube editor if you want a stricter judge cut (current file is ~3:37).

---

## After free Alibaba reclaim (if you get a VM tonight)

```text
PUBLIC_URL=http://<PUBLIC_IP>:8000
Health=http://<PUBLIC_IP>:8000/v1/health
```

Update `docs/PROOF_OF_ALIBABA_DEPLOYMENT.md`, replace Workbench PNG, push to `kenhuangus/continuum`, then paste PUBLIC_URL into Devpost testing instructions.
