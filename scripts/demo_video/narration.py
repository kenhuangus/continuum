"""Long-form Continuum product tour — field-level deep dive (product-only narration)."""
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
            "Memory Graph, Packer Lab, and Policies — and explains the important fields as we go."
        ),
    },
    {
        "id": "02_chat_fields",
        "frame": "02_chat_fields.png",
        "audio": "beat_02.wav",
        "chapter": "Chat — workspace & session",
        "text": (
            "Start on Chat. The Workspace field scopes every memory write and retrieve — "
            "think of it as the shared memory namespace agents share. Session identifies the "
            "current conversation thread; it can reset without wiping workspace memory. Org "
            "binds tenancy when auth is on; API Key is optional for local demo, and maps to "
            "role-aware access when keys are configured. These four fields are how Continuum "
            "keeps memory multi-tenant and session-aware."
        ),
    },
    {
        "id": "03_budget_algo",
        "frame": "03_budget_algo.png",
        "audio": "beat_03.wav",
        "chapter": "Chat — budget & packer",
        "text": (
            "The Budget slider caps how many memory tokens enter the model context. That is "
            "deliberate context engineering — not infinite paste. Packer chooses the algorithm: "
            "type_quota keeps typed balances, greedy fills by score, and mmr adds diversity. "
            "New Session clears the chat log but keeps workspace memories. Run Forgetting Pass "
            "retires stale facts on purpose from this same screen."
        ),
    },
    {
        "id": "04_session_a_vip",
        "frame": "04_session_a_vip.png",
        "audio": "beat_04.wav",
        "chapter": "Session A — VIP",
        "text": (
            "Type into Message Input and Send: Remember — Acme is a VIP customer. Continuum "
            "ingests that as a durable typed memory, not disposable chat history. Watch the "
            "Memory Inspector on the right fill with an active card you can select and inspect."
        ),
    },
    {
        "id": "05_session_a_discount",
        "frame": "05_session_a_discount.png",
        "audio": "beat_05.wav",
        "chapter": "Session A — discount",
        "text": (
            "Next: Remember — approved twelve percent discount for Acme through end of twenty "
            "twenty-six. Commercial terms become first-class memories so later sessions can "
            "retrieve them without re-prompting the entire history. Continuum also detects "
            "contradictions and can supersede older slot values when facts change."
        ),
    },
    {
        "id": "06_session_a_pref",
        "frame": "06_session_a_pref.png",
        "audio": "beat_06.wav",
        "chapter": "Session A — preference + Active",
        "text": (
            "And a preference: Acme prefers email over phone. Open the Active tab in the "
            "inspector — VIP, discount, and channel sit as typed memories Continuum will pack "
            "into context. Citations on answers will point back to these memory ids, so every "
            "reply is auditable."
        ),
    },
    {
        "id": "07_new_session",
        "frame": "07_new_session.png",
        "audio": "beat_07.wav",
        "chapter": "New session",
        "text": (
            "Click New Session. The Session field rotates to a fresh id and the chat log clears — "
            "no pasted history, no hidden system dump of the old thread. Workspace memories stay "
            "alive underneath. If memory were only the conversation window, Acme's VIP status "
            "and discount would already be gone."
        ),
    },
    {
        "id": "08_recall_citations",
        "frame": "08_recall_citations.png",
        "audio": "beat_08.wav",
        "chapter": "Cross-session recall & citations",
        "text": (
            "In the new session ask: What discount does Acme get, and are they VIP? Continuum "
            "hybrid-retrieves candidates with BM25 and ANN, packs under the budget slider, and "
            "answers from memory — with citation chips on the reply linking memory ids. That is "
            "cross-session continuity you can verify live."
        ),
    },
    {
        "id": "09_packer_chat",
        "frame": "09_packer_chat.png",
        "audio": "beat_09.wav",
        "chapter": "Context Packer panel",
        "text": (
            "Below the inspector, the Context Packer panel shows the token meter — used versus "
            "budget — plus algorithm, candidate count, and which memories made the cut. Tighten "
            "the budget and less relevant memories stay out on purpose. This is the same packing "
            "engine Packer Lab exposes for experiments."
        ),
    },
    {
        "id": "10_inspector_tabs",
        "frame": "10_inspector_tabs.png",
        "audio": "beat_10.wav",
        "chapter": "Inspector lifecycle tabs",
        "text": (
            "Cycle the inspector tabs: Active holds current truth, Superseded shows replaced "
            "slot values after contradictions, and Forgotten shows retired facts. Continuum "
            "keeps the lifecycle inspectable instead of deleting history silently — memory that "
            "never forgets is a liability; memory you cannot audit is worse."
        ),
    },
    {
        "id": "11_memory_graph",
        "frame": "11_memory_graph.png",
        "audio": "beat_11.wav",
        "chapter": "Memory Graph — overview",
        "text": (
            "Navigate to Memory Graph. Workspace Stats summarize active, superseded, and "
            "forgotten counts, plus entities and edges. The graph stage draws entity nodes and "
            "supersession links so contradiction and lifecycle are visible — not buried in logs. "
            "Click Refresh to reload stats after chat writes."
        ),
    },
    {
        "id": "12_graph_filters",
        "frame": "12_graph_filters.png",
        "audio": "beat_12.wav",
        "chapter": "Memory Graph — filters & detail",
        "text": (
            "Use the graph status filters — Active, Superseded, Forgotten — to focus the memory "
            "list. Select a memory to open detail: slots, policy tags, and pack-inclusion explain. "
            "Supersession edges from earlier Acme facts should appear after the chat tour, "
            "showing how Continuum links replaced values instead of losing them."
        ),
    },
    {
        "id": "13_packer_lab_fields",
        "frame": "13_packer_lab_fields.png",
        "audio": "beat_13.wav",
        "chapter": "Packer Lab — controls",
        "text": (
            "Open Packer Lab. Query is the retrieval prompt — same hybrid BM25 plus ANN path "
            "chat uses. Budget tokens caps the pack. Algorithm picks type_quota, greedy, or mmr. "
            "As-of is point-in-time retrieval: ask what was true at a past timestamp. Run pack "
            "preview builds a candidate set and a packed set with explanations; Explain selected "
            "returns structured inclusion reasons for one memory."
        ),
    },
    {
        "id": "14_packer_run_tight",
        "frame": "14_packer_run_tight.png",
        "audio": "beat_14.wav",
        "chapter": "Packer Lab — tight budget",
        "text": (
            "Run pack preview with a tight budget. The token meter and meta line show tokens used "
            "versus budget, candidate count, and why items were included or dropped. Under a "
            "small budget, Continuum keeps only the highest-value Acme facts — VIP and discount "
            "outrank weaker candidates."
        ),
    },
    {
        "id": "15_packer_run_wide",
        "frame": "15_packer_run_wide.png",
        "audio": "beat_15.wav",
        "chapter": "Packer Lab — wider budget",
        "text": (
            "Raise the budget and run again. More candidates fit; explanations and the packed "
            "list expand. Comparing two budgets side by side is how you tune agent context without "
            "guessing. Switch algorithm to mmr when you need diversity across memory types."
        ),
    },
    {
        "id": "16_policies_rbac",
        "frame": "16_policies_rbac.png",
        "audio": "beat_16.wav",
        "chapter": "Policies — org & RBAC",
        "text": (
            "Policies covers governance. Org and API Key in the top bar bind tenancy and RBAC "
            "lite — reader, writer, or admin when keys are mapped. Check health to confirm the "
            "API is reachable. Scan policy tags to surface PII and short-retention heuristics "
            "attached on write. Pack can exclude PII when the exclude-PII policy is enabled."
        ),
    },
    {
        "id": "17_policies_forget",
        "frame": "17_policies_forget.png",
        "audio": "beat_17.wav",
        "chapter": "Policies — forget & consolidate",
        "text": (
            "Run Forgetting Pass to retire stale or policy-expired facts. Consolidate merges "
            "redundant groups so the workspace stays lean. The admin log shows what changed. "
            "Hybrid retrieve is summarized here too: every pack uses BM25 plus ANN candidates, "
            "optional graph expansion, then budget packing — never whole-workspace paste."
        ),
    },
    {
        "id": "18_close",
        "frame": "18_close.png",
        "audio": "beat_18.wav",
        "chapter": "Close",
        "text": (
            "Back on Chat, Continuum ties it together: typed memories, hybrid retrieve, budget "
            "packing with explanations, citations, supersession, forgetting, graph links, "
            "consolidate, as-of queries, and policy-aware controls — a memory OS agents share "
            "over HTTP. That is Continuum."
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
        print(f"  {b['id']}: {len(b['text'].split())} words -> {b['frame']} ({b['chapter']})")
