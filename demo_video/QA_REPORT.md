# Continuum demo video — sync QA

- File: `continuum_demo.mp4`
- Tolerance: **0.15s** per chapter
- Method: `qa_clips`
- Overall: **PASS**
- Total audio: 217.050s · total video: 217.000s (Δ 0.050s) — PASS

| # | Chapter | Audio (s) | Video seg (s) | |Δ| (s) | Result |
|---|---------|-----------|---------------|--------|--------|
| 1 | 01_intro — Product intro | 15.220 | 15.220 | 0.000 | PASS |
| 2 | 02_chat_fields — Chat — workspace & session | 15.820 | 15.820 | 0.000 | PASS |
| 3 | 03_budget_algo — Chat — budget & packer | 14.730 | 14.720 | 0.010 | PASS |
| 4 | 04_session_a_vip — Session A — VIP | 9.210 | 9.200 | 0.010 | PASS |
| 5 | 05_session_a_discount — Session A — discount | 10.890 | 10.880 | 0.010 | PASS |
| 6 | 06_session_a_pref — Session A — preference + Active | 10.060 | 10.060 | 0.000 | PASS |
| 7 | 07_new_session — New session | 10.990 | 10.990 | 0.000 | PASS |
| 8 | 08_recall_citations — Cross-session recall & citations | 11.390 | 11.390 | 0.000 | PASS |
| 9 | 09_packer_chat — Context Packer panel | 10.500 | 10.500 | 0.000 | PASS |
| 10 | 10_inspector_tabs — Inspector lifecycle tabs | 11.000 | 11.000 | 0.000 | PASS |
| 11 | 11_memory_graph — Memory Graph — overview | 11.380 | 11.380 | 0.000 | PASS |
| 12 | 12_graph_filters — Memory Graph — filters & detail | 12.090 | 12.080 | 0.010 | PASS |
| 13 | 13_packer_lab_fields — Packer Lab — controls | 15.720 | 15.720 | 0.000 | PASS |
| 14 | 14_packer_run_tight — Packer Lab — tight budget | 10.460 | 10.460 | 0.000 | PASS |
| 15 | 15_packer_run_wide — Packer Lab — wider budget | 9.630 | 9.630 | 0.000 | PASS |
| 16 | 16_policies_rbac — Policies — org & RBAC | 13.700 | 13.700 | 0.000 | PASS |
| 17 | 17_policies_forget — Policies — forget & consolidate | 12.850 | 12.840 | 0.010 | PASS |
| 18 | 18_close — Close | 11.410 | 11.400 | 0.010 | PASS |

## Notes

Sync model: each chapter still/clip duration equals ffprobe duration of that chapter's TTS audio.
Continuous screencast mux is disabled for the final mp4 (visuals would race ahead of narration).

