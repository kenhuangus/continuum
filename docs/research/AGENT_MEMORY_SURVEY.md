# Agent Memory Survey — Continuum Upgrade Basis

**Date:** 2026-07-18  
**Purpose:** Science-honest map of agent-memory literature and industry practice, grounded against Continuum’s current codebase.  
**Honesty rule:** Citations below are for *design inspiration*. Continuum only claims techniques that are implemented and eval-gated in-repo.

---

## 1. Seminal & recent papers (curated)

### Foundational / cognitive framing

| Work | Venue / year | Core idea | Continuum relevance |
|------|--------------|-----------|---------------------|
| Tulving — episodic vs semantic | Classic cog. sci. | Distinct memory systems | Our `MemoryType` taxonomy |
| Park et al. — *Generative Agents* | UIST 2023 | Memory stream + **recency × importance × relevance** retrieval; periodic reflection | **P0 scoring**; reflection stub |
| Shinn et al. — *Reflexion* | NeurIPS 2023 | Verbal self-critique stored as episodic feedback | Write critic / outcome writeback |
| Packer et al. — *MemGPT* | arXiv 2023 → **Letta** product | OS-style paging: main context / recall / archival | Pack-as-RAM; working vs warm store |
| Zhong et al. — *MemoryBank* | AAAI 2024 | Dual-tower long-term user memory + Ebbinghaus-style forgetting | Decay / consolidation |
| Wang et al. survey | arXiv 2404.13501 | Unified survey of LLM-agent memory ops | Taxonomy backbone |
| Gutiérrez et al. — *HippoRAG* | NeurIPS 2024 | KG + Personalized PageRank multi-hop | Entity/graph edges (P1) |
| Xu et al. — *A-MEM* | 2025 | Zettelkasten-like evolving note graph | Link notes on write |
| Chhikara et al. — *Mem0* | arXiv 2504.19413 | Production extract/update/search memory layer | SaaS API/MCP shape |
| ACL Findings 2026 — *From Storage to Experience* | ACL 2026 | Storage → Reflection → Experience evolution | Distill episodic→semantic |
| Weiß — *Agent Memory Research in 2026* | Open MIND 2026 | Extended taxonomy + eval gaps | Eval protocol honesty |

### Adjacent / still influential

- **Voyager** (Wang et al., 2023) — skill library as procedural memory  
- **RET-LLM / LongMem / MemoryLLM** — parametric + external hybrid (we stay *external store only*)  
- **SCM / structured memory** — slot/key facts (we already use `slots`)  
- **LoCoMo, LongMemEval, MemoryAgentBench** — conversational / long-horizon eval suites (we use a smaller offline fixture suite)

---

## 2. Industry / lab practice (public)

| Org / product | Public stance | Lesson for Continuum |
|---------------|---------------|----------------------|
| **OpenAI** ChatGPT Memory | Consumer “remembered facts” + history; not a portable Memory OS | Prefer **MCP/API substrate** over platform lock-in |
| **Anthropic** | MCP (Nov 2024+) as tool bus; memory as external tool | First-class MCP tools + workspace isolation |
| **Google DeepMind** | Long-context + agents; less open “memory SaaS” | Don’t confuse long context with governed memory |
| **Meta** | Generative Agents lineage; open research culture | Keep retrieval scoring transparent |
| **Microsoft Research** | Semantic Kernel / AutoGen memory plugins | Pluggable store + pack algorithms |
| **Letta (MemGPT)** | Self-editing memory, sleep-time compute | Optional consolidation job |
| **Mem0** | Managed add/search/update/delete; graph variant Mem0g | Clean REST + SDK contracts |
| **Zep / Graphiti** | Temporal knowledge graphs, bi-temporal facts | Edges + `effective_from`/`to` |
| **LangGraph Store / LangMem** | Framework-native semantic/episodic/procedural | Match type taxonomy; stay framework-agnostic via MCP |

---

## 3. Taxonomy of approaches

### 3.1 By cognitive type

| Type | Definition | Continuum today |
|------|------------|-----------------|
| **Working / short-term** | Prompt-resident state | Pack output only (no Redis working tier) |
| **Episodic** | Time-stamped events / turns | `MemoryType.EPISODIC` + session source |
| **Semantic** | Distilled facts | `SEMANTIC` + slots |
| **Preference** | User/org prefs | `PREFERENCE` |
| **Procedural** | How-to / playbooks | `PROCEDURAL` (little learning loop) |
| **Decision** | Binding commitments | `DECISION` + supersession |
| **Artifact refs** | Pointers to docs | `ARTIFACT_REF` |

### 3.2 By structure

| Structure | Examples | Continuum |
|-----------|----------|-----------|
| Flat vector store | Classic RAG | Dense channel via local/API embeddings |
| Sparse / keyword | BM25, substring | Sparse retrieve (not true BM25 index yet) |
| Entity / slot | Entity-centric banks | `entities`, `slots`, entity boost |
| Graph / multi-hop | HippoRAG, A-MEM, Zep | Supersession edges only (P0→P1 expand) |
| Hierarchical / OS paging | MemGPT, MemoryOS | Type quotas + pack budget ≈ soft paging |
| Parametric | MemoryLLM | Out of scope |

### 3.3 By dynamics

| Dynamic | Literature | Continuum |
|---------|------------|-----------|
| Write / extract | Mem0, MemoryBank | Heuristic + optional LLM + critic |
| Conflict / update | Mem0g, Graphiti | Slot supersession |
| Retrieve score | Generative Agents R×I×R | Utility×confidence + keywords (**gap**) |
| Pack / budget | Knapsack / MMR RAG | greedy, type_quota, knapsack_dp, mmr |
| Forget / decay | MemoryBank, Ebbinghaus | TTL expire + linear confidence decay |
| Reflect / consolidate | Generative Agents, Reflexion | **Missing → P0 stub** |
| Utility learning | Outcome reinforcement | Tiny +0.02 bump on pack use |

### 3.4 By access pattern (SaaS)

```
Agent ──MCP tools──► Continuum Memory OS
Agent ──HTTP /v1/*──► Continuum Memory OS
         │
         ├─ Auth (API key) + workspace isolation
         ├─ remember / search / pack / forget / consolidate
         └─ Eval metrics (recall@budget, stale leakage)
```

---

## 4. Continuum vs literature — gap analysis

### Already present (honest)

- Typed memory schema with provenance fields  
- Retrieve-then-pack (hybrid sparse ∪ dense candidate pool)  
- Slot-aware supersession (`supersedes: list[str]`)  
- Multi-algorithm packer under token budget  
- Forgetting pass + audit events  
- Offline eval fixtures with naive baseline comparison  
- API keys, rate limit, request IDs, MCP stdio tools  
- Injection sanitize on packed context (basic)

### Material gaps (science)

| Gap | Why it matters | Priority |
|-----|----------------|----------|
| No Generative-Agents-style **importance/recency/relevance** joint score | Packer still heuristic; literature’s most cited retrieval formula | **P0** |
| Dense path still **scans all active rows** | Not HippoRAG/MemGPT-scale; O(n) embeddings | **P0** (cap + cache; true ANN = P2) |
| No **reflection / episodic→semantic distill** | Missing Storage→Reflection stage (ACL 2026 framing) | **P0** stub / job |
| No **memory graph** beyond supersession | Blocks multi-hop recall (HippoRAG) | **P1** |
| Importance not LLM-rated; `utility` underused | Weak “poignancy” signal | **P0** heuristic + optional LLM |
| Eval lacks ablations & literature metrics naming | Can’t claim “research-grade” without R@k, leakage, ablation table | **P0** |
| No true BM25 / inverted index | Sparse is substring/token | **P1** |
| No sleep-time / async consolidation queue | Letta differentiator | **P1** |
| Postgres prod path incomplete | SaaS durability | **P1** |
| OAuth / org RBAC | Multi-tenant SaaS | **P2** |

---

## 5. Prioritized techniques for a hackathon-quality, science-honest Memory OS

### P0 — implement this loop

1. **Importance × Recency × Relevance scoring** (Park et al. 2023 formula; equal α=1; min-max normalize within candidate set).  
   - Recency: exp decay on hours since `last_accessed_at` (decay≈0.995).  
   - Importance: map from `utility`/`confidence`/type prior (+ optional LLM 1–10 later).  
   - Relevance: dense cosine + sparse overlap.  
2. **Retrieve-then-pack with capped candidate pool** (already started — strengthen scoring + entity channel + score explanations).  
3. **Consolidation stub**: `consolidate(workspace_id)` that groups episodic by entity and writes 1 semantic summary memory (heuristic; LLM optional).  
4. **Eval expansion**: recall@budget, stale leakage, ablation (`no_rir`, `sparse_only`, `dense_only`, `no_pack`), Continuum ≥ naive.  
5. **MCP/HTTP contract doc + pack/consolidate endpoints** usable by any coding agent.

### P1 — next loop

1. Explicit **memory graph edges** table (`related_to`, `mentions_entity`, `supersedes`) + 1-hop expansion in retrieve.  
2. True **BM25** or inverted index over workspace.  
3. Async consolidation / “sleep” job.  
4. Postgres store implementation behind `create_store`.  
5. Faithfulness / NLI conflict critic beyond slots.

### P2 — differentiators (do not claim early)

1. Personalized PageRank / HippoRAG-class multi-hop.  
2. ANN vector DB (FAISS/Qdrant).  
3. Utility learning from labeled outcomes.  
4. Full policy/PII engine + GDPR subject erase.  
5. Billing meters.

---

## 6. What we will *not* claim

- We do **not** claim HippoRAG PPR, MemGPT sleep-time compute, or Mem0 production accuracy until code + evals exist.  
- Local hashed embeddings ≠ text-embedding-v3 quality offline.  
- Eval suite is **fixture-based**, not LoCoMo/LongMemEval parity.  
- Alibaba free-tier cloud deploy is blocked; local/Docker proof only.

---

## 7. References (short list)

1. Park et al., *Generative Agents*, UIST 2023.  
2. Shinn et al., *Reflexion*, NeurIPS 2023.  
3. Packer et al., *MemGPT*, 2023; Letta productization.  
4. Zhong et al., *MemoryBank*, AAAI 2024.  
5. Gutiérrez et al., *HippoRAG*, NeurIPS 2024.  
6. Xu et al., *A-MEM*, 2025.  
7. Chhikara et al., *Mem0*, arXiv:2504.19413, 2025.  
8. Wang et al., *A Survey on the Memory Mechanism of LLM-based Agents*, 2024.  
9. ACL Findings 2026, *From Storage to Experience*.  
10. Rasmussen et al. / Zep Graphiti temporal graphs (product + papers 2025).  

---

*Next document:* [`IMPROVEMENT_PLAN.md`](./IMPROVEMENT_PLAN.md) — executable tasks for all coding agents.
