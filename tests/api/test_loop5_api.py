from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.api


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CONTINUUM_DB_PATH", str(tmp_path / "loop5.db"))
    monkeypatch.setenv("CONTINUUM_AUTH_DISABLED", "1")
    monkeypatch.setenv("CONTINUUM_FORCE_LOCAL_EMBED", "1")
    # Reload app with fresh env
    import importlib
    import continuum_api.main as main

    importlib.reload(main)
    return TestClient(main.app)


def test_openai_tools_list_and_call(client):
    r = client.get("/v1/openai/tools")
    assert r.status_code == 200
    tools = r.json()["tools"]
    names = {t["function"]["name"] for t in tools}
    assert "memory_search" in names
    assert "memory_outcome" in names

    remember = client.post(
        "/v1/openai/tools/call",
        json={
            "name": "memory_remember",
            "arguments": {
                "workspace_id": "ws_oa",
                "content": "Approved 10% discount for Nova.",
                "type": "decision",
                "entities": ["Nova"],
            },
        },
    )
    assert remember.status_code == 200
    mid = remember.json()["result"]["id"]

    pack = client.post(
        "/v1/openai/tools/call",
        json={
            "name": "memory_pack_preview",
            "arguments": {"workspace_id": "ws_oa", "query": "Nova discount", "budget": 400},
        },
    )
    assert pack.status_code == 200
    assert pack.json()["result"]["memories"]

    outcome = client.post(
        "/v1/openai/tools/call",
        json={
            "name": "memory_outcome",
            "arguments": {
                "workspace_id": "ws_oa",
                "memory_ids": [mid],
                "success": True,
            },
        },
    )
    assert outcome.status_code == 200
    assert outcome.json()["result"]["updated"]


def test_chat_stream_sse_events(client):
    # Seed via remember tool path
    client.post(
        "/v1/memories",
        json={
            "workspace_id": "ws_sse",
            "content": "Acme is a VIP customer.",
            "type": "preference",
            "entities": ["Acme"],
        },
    )
    with client.stream(
        "POST",
        "/v1/chat/stream",
        json={
            "workspace_id": "ws_sse",
            "session_id": "s1",
            "message": "Is Acme VIP?",
            "memory_token_budget": 400,
        },
    ) as resp:
        assert resp.status_code == 200
        body = "".join(resp.iter_text())
    assert "event: pack" in body
    assert "event: reply" in body
    assert "event: done" in body


def test_async_consolidate_endpoint(client):
    for i in range(2):
        client.post(
            "/v1/memories",
            json={
                "workspace_id": "ws_async",
                "content": f"Acme episodic note number {i} about pricing.",
                "type": "episodic",
                "entities": ["Acme"],
            },
        )
    r = client.post(
        "/v1/memories/consolidate/async",
        json={"workspace_id": "ws_async", "max_groups": 5},
    )
    assert r.status_code == 200
    job_id = r.json()["job_id"]
    status = client.get(f"/v1/memories/consolidate/jobs/{job_id}")
    assert status.status_code == 200
    assert status.json()["job_id"] == job_id
