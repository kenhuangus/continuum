"""Beat script for the Continuum Track 1 MemoryAgent demo (~3 min English)."""
from __future__ import annotations

from typing import TypedDict


class Beat(TypedDict):
    id: str
    frame: str
    audio: str
    text: str


BEATS: list[Beat] = [
    {
        "id": "01_problem",
        "frame": "01_hero.png",
        "audio": "beat_01.wav",
        "text": (
            "Most AI agents forget everything between sessions. You teach them that Acme is a VIP, "
            "approve a discount, set a communication preference — then open a new chat and it's gone. "
            "Judges see the same failure in demos every day: scrollback is not memory, and a longer "
            "context window is not a memory operating system. Continuum is built for Track One, "
            "MemoryAgent: typed memories that persist across sessions, pack under a token budget, "
            "forget on purpose, and cite which memories shaped the answer. Here is the happy path "
            "on the live Continuum UI."
        ),
    },
    {
        "id": "02_session_a_vip",
        "frame": "02_session_a_vip.png",
        "audio": "beat_02.wav",
        "text": (
            "Watch Session A on the Continuum demo UI. We set a workspace and tell the agent: "
            "Remember — Acme is a VIP customer. That fact is ingested as a durable memory with "
            "workspace scope, not just chat scrollback that dies when the thread ends. The inspector "
            "on the right starts to fill as Continuum stores what matters for later sessions — "
            "exactly the continuity MemoryAgent demos need to show."
        ),
    },
    {
        "id": "03_session_a_discount",
        "frame": "03_session_a_discount.png",
        "audio": "beat_03.wav",
        "text": (
            "Next decision: Remember — approved twelve percent discount for Acme through end of "
            "twenty twenty-six. Commercial terms become first-class memories, so later sessions can "
            "retrieve them without re-prompting the entire history or hoping the model still has it "
            "in context. Preferences and decisions should survive a new session id — that is the bar."
        ),
    },
    {
        "id": "04_session_a_email",
        "frame": "04_session_a_email.png",
        "audio": "beat_04.wav",
        "text": (
            "And a preference: Acme prefers email communication over phone. Three memories — VIP "
            "status, discount, and channel. Open the Active tab in the memory inspector: you see the "
            "cards Continuum will pack into context. This is the difference between a chatbot "
            "transcript and a real memory layer judges can inspect while the product runs."
        ),
    },
    {
        "id": "05_new_session",
        "frame": "05_new_session.png",
        "audio": "beat_05.wav",
        "text": (
            "Now the hard part. Click New Session. Session B starts with a clean chat log — no pasted "
            "history, no hidden system dump of the old thread. If memory were only the conversation "
            "window, Acme's VIP status and discount would already be gone. Continuum keeps the "
            "workspace memories alive underneath, ready for retrieval on the next turn."
        ),
    },
    {
        "id": "06_session_b_recall",
        "frame": "06_session_b_recall.png",
        "audio": "beat_06.wav",
        "text": (
            "In Session B we ask: What discount does Acme get, and are they VIP? Continuum retrieves "
            "candidates, packs under budget, and answers from memory — citing the stored facts. You "
            "see the agent recall twelve percent and VIP without us re-teaching anything. That is "
            "cross-session continuity judges can verify live in the product, not a scripted mockup."
        ),
    },
    {
        "id": "07_packer_panel",
        "frame": "07_packer_panel.png",
        "audio": "beat_07.wav",
        "text": (
            "Look at the packer panel. Continuum hybrid-retrieves candidates, then packs under a "
            "token budget — algorithm, tokens used, and which memories made the cut. When budget is "
            "tight, less relevant memories stay out of context on purpose. Memory is not infinite "
            "paste; it is deliberate context engineering for agents that must stay inside limits."
        ),
    },
    {
        "id": "08_forget_cta",
        "frame": "08_forget_or_tabs.png",
        "audio": "beat_08.wav",
        "text": (
            "Memory that never forgets is a liability. Continuum runs forgetting and supersession — "
            "stale facts retire; active, superseded, and forgotten tabs make the lifecycle visible. "
            "Built on Qwen Cloud APIs for generation and speech, Continuum is an open Memory OS any "
            "agent can share via HTTP or MCP. Agents that remember — and forget on purpose. That is "
            "Continuum for the Qwen Cloud MemoryAgent track."
        ),
    },
]


def word_count() -> int:
    return sum(len(b["text"].split()) for b in BEATS)


def estimated_duration_seconds(words_per_minute: float = 145.0) -> float:
    return word_count() / words_per_minute * 60.0


if __name__ == "__main__":
    wc = word_count()
    print(f"beats={len(BEATS)} words={wc} ~{estimated_duration_seconds():.0f}s @145wpm")
    for b in BEATS:
        print(f"  {b['id']}: {len(b['text'].split())} words -> {b['frame']}")
