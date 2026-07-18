# Continuum demo video

- Output: `continuum_demo.mp4`
- TTS mode: `edge`
- Narration speed: **1.8x** (ffmpeg `atempo` applied after TTS)
- Beats: 18 · words: 895 · ~206s wall-clock

## Chapters

1. **00:00** — Product intro (`01_intro`)
2. **00:15** — Chat — workspace & session (`02_chat_fields`)
3. **00:31** — Chat — budget & packer (`03_budget_algo`)
4. **00:45** — Session A — VIP (`04_session_a_vip`)
5. **00:55** — Session A — discount (`05_session_a_discount`)
6. **01:05** — Session A — preference + Active (`06_session_a_pref`)
7. **01:15** — New session (`07_new_session`)
8. **01:26** — Cross-session recall & citations (`08_recall_citations`)
9. **01:37** — Context Packer panel (`09_packer_chat`)
10. **01:48** — Inspector lifecycle tabs (`10_inspector_tabs`)
11. **01:58** — Memory Graph — overview (`11_memory_graph`)
12. **02:08** — Memory Graph — filters & detail (`12_graph_filters`)
13. **02:20** — Packer Lab — controls (`13_packer_lab_fields`)
14. **02:34** — Packer Lab — tight budget (`14_packer_run_tight`)
15. **02:44** — Packer Lab — wider budget (`15_packer_run_wide`)
16. **02:53** — Policies — org & RBAC (`16_policies_rbac`)
17. **03:06** — Policies — forget & consolidate (`17_policies_forget`)
18. **03:17** — Close (`18_close`)

## Re-run

```powershell
.venv\Scripts\python.exe scripts\demo_video\run_pipeline.py
```

Flags: `--skip-capture`, `--skip-tts`, `--silent`, `--screencast-mux` (sync-unsafe),
`--no-ken-burns`, `--speed 1.8`, `--base-url URL`.

Assemble uses **per-chapter stills timed to TTS audio** (sync-correct).

