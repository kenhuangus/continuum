"""Long-form Continuum product tour narration (no competition / vendor track wording)."""
from __future__ import annotations

from typing import TypedDict

# Wall-clock target assumes ~1.8x playback of a ~145 wpm base voice.
NARRATION_SPEED = 1.8


class Beat(TypedDict):
    id: str
    frame: str
    audio: str
    text: str
    # Optional UI hint for capture (view name / action label)
    chapter: str


BEATS: list[Beat] = [
    {
        "id": "01_intro",
        "frame": "01_hero.png",
        "audio": "beat_01.wav",
        "chapter": "Product intro",
        "text": (
            "Continuum is a memory operating system for agents. Scrollback is not memory, "
            "and a longer context window is not a memory layer. Continuum stores typed memories "
            "that persist across sessions, packs them under a token budget, forgets on purpose, "
            "and cites which facts shaped each answer. This tour walks the live product — Chat, "
            "Memory Graph, Packer Lab, and Policies — so you can see every innovation in the UI."
        ),
    },
    {
        "id": "02_session_a_vip",
        "frame": "02_session_a_vip.png",
        "audio": "beat_02.wav",
        "chapter": "Session A — VIP",
        "text": (
            "In Chat, we stay on Session A and tell Continuum: Remember — Acme is a VIP customer. "
            "That fact is ingested as a durable workspace memory, not chat history that dies when "
            "the thread ends. The Memory Inspector on the right fills with an active card you can "
            "inspect by type and status."
        ),
    },
    {
        "id": "03_session_a_discount",
        "frame": "03_session_a_discount.png",
        "audio": "beat_03.wav",
        "chapter": "Session A — discount",
        "text": (
            "Next: Remember — approved twelve percent discount for Acme through end of twenty "
            "twenty-six. Commercial terms become first-class memories, so later sessions can "
            "retrieve them without re-prompting the entire history. Continuum also detects "
            "contradictions and can supersede older slot values when facts change."
        ),
    },
    {
        "id": "04_session_a_pref",
        "frame": "04_session_a_pref.png",
        "audio": "beat_04.wav",
        "chapter": "Session A — preference",
        "text": (
            "And a preference: Acme prefers email over phone. Open the Active tab in the inspector — "
            "VIP, discount, and channel sit as typed memories Continuum will pack into context. "
            "Citations on answers will point back to these memory ids, so every reply is auditable."
        ),
    },
    {
        "id": "05_new_session",
        "frame": "05_new_session.png",
        "audio": "beat_05.wav",
        "chapter": "New session",
        "text": (
            "Click New Session. Session B starts with a clean chat log — no pasted history, no hidden "
            "system dump of the old thread. Workspace memories stay alive underneath. If memory were "
            "only the conversation window, Acme's VIP status and discount would already be gone."
        ),
    },
    {
        "id": "06_recall_citations",
        "frame": "06_recall_citations.png",
        "audio": "beat_06.wav",
        "chapter": "Cross-session recall",
        "text": (
            "In Session B we ask: What discount does Acme get, and are they VIP? Continuum hybrid-"
            "retrieves candidates with BM25 and ANN, packs under the budget slider, and answers from "
            "memory — with citations on the reply. Cross-session continuity you can verify live."
        ),
    },
    {
        "id": "07_packer_chat",
        "frame": "07_packer_chat.png",
        "audio": "beat_07.wav",
        "chapter": "Budget packer",
        "text": (
            "Watch the Context Packer panel and token meter. Algorithm, tokens used versus budget, "
            "candidate count, and which memories made the cut are visible. When budget is tight, "
            "less relevant memories stay out of context on purpose — deliberate context engineering, "
            "not infinite paste."
        ),
    },
    {
        "id": "08_memory_graph",
        "frame": "08_memory_graph.png",
        "audio": "beat_08.wav",
        "chapter": "Memory Graph",
        "text": (
            "Navigate to Memory Graph. Workspace stats show active, superseded, and forgotten counts, "
            "plus entities and edges. The graph links related memories and supersession edges so "
            "contradiction and lifecycle are visible — not buried in logs."
        ),
    },
    {
        "id": "09_packer_lab",
        "frame": "09_packer_lab.png",
        "audio": "beat_09.wav",
        "chapter": "Packer Lab",
        "text": (
            "Open Packer Lab. Run pack preview with a query, algorithm, and optional as-of timestamp "
            "for point-in-time retrieval. Explanations show why each memory was included. Explain "
            "on a selected memory returns structured inclusion reasons and cite overlap."
        ),
    },
    {
        "id": "10_policies_forget",
        "frame": "10_policies_forget.png",
        "audio": "beat_10.wav",
        "chapter": "Policies & forgetting",
        "text": (
            "In Policies, run a forgetting pass and optional consolidate. Stale facts retire; "
            "policy tags mark PII and short retention heuristically. Org and role-aware access "
            "apply when API keys are configured. Memory that never forgets is a liability — "
            "Continuum forgets on purpose and keeps the lifecycle inspectable."
        ),
    },
    {
        "id": "11_close",
        "frame": "11_close.png",
        "audio": "beat_11.wav",
        "chapter": "Close",
        "text": (
            "Continuum: typed memories, hybrid retrieve, budget packing with explanations, "
            "citations, supersession, forgetting, graph links, consolidate, as-of queries, and "
            "policy-aware controls — a memory OS agents can share over HTTP. That is Continuum."
        ),
    },
]


def word_count() -> int:
    return sum(len(b["text"].split()) for b in BEATS)


def estimated_duration_seconds(
    words_per_minute: float = 145.0,
    speed: float = NARRATION_SPEED,
) -> float:
    """Wall-clock estimate after applying narration speed (default 1.8x)."""
    base = word_count() / words_per_minute * 60.0
    return base / max(speed, 0.1)


if __name__ == "__main__":
    wc = word_count()
    print(
        f"beats={len(BEATS)} words={wc} "
        f"~{estimated_duration_seconds():.0f}s wall @145wpm ×{NARRATION_SPEED}"
    )
    for b in BEATS:
        print(f"  {b['id']}: {len(b['text'].split())} words → {b['frame']} ({b['chapter']})")
