from __future__ import annotations

import pytest

pytestmark = pytest.mark.api


def test_health_ok(api_client):
    r = api_client.get("/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["service"] == "continuum"


def test_create_and_list_memory(api_client, unique_workspace_id: str):
    create = api_client.post(
        "/v1/memories",
        json={
            "workspace_id": unique_workspace_id,
            "content": "Acme is a VIP customer",
            "type": "semantic",
            "entities": ["Acme"],
        },
    )
    assert create.status_code == 200
    mem = create.json()
    assert mem["content"] == "Acme is a VIP customer"
    assert mem["workspace_id"] == unique_workspace_id

    listed = api_client.get("/v1/memories", params={"workspace_id": unique_workspace_id})
    assert listed.status_code == 200
    memories = listed.json()["memories"]
    assert any(m["id"] == mem["id"] for m in memories)


def test_workspace_isolation(api_client):
    ws_a = "ws-iso-a-" + "x" * 8
    ws_b = "ws-iso-b-" + "y" * 8

    created = api_client.post(
        "/v1/memories",
        json={"workspace_id": ws_a, "content": "Secret only in A", "type": "semantic"},
    )
    assert created.status_code == 200
    mem_id = created.json()["id"]

    in_a = api_client.get("/v1/memories", params={"workspace_id": ws_a}).json()["memories"]
    in_b = api_client.get("/v1/memories", params={"workspace_id": ws_b}).json()["memories"]

    assert any(m["id"] == mem_id for m in in_a)
    assert not any(m["id"] == mem_id for m in in_b)


def test_chat_returns_expected_keys(api_client, unique_workspace_id: str):
    r = api_client.post(
        "/v1/chat",
        json={
            "workspace_id": unique_workspace_id,
            "session_id": "sess-chat-1",
            "message": "Remember: Acme prefers email.",
            "memory_token_budget": 800,
            "packer": "type_quota",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert "reply" in body
    assert "pack_meta" in body
    assert "citations" in body
    assert "memories_packed" in body
    assert "memories_written" in body
    assert "algorithm" in body["pack_meta"]
    assert "token_estimate" in body["pack_meta"]


def test_pack_preview(api_client, unique_workspace_id: str):
    api_client.post(
        "/v1/memories",
        json={
            "workspace_id": unique_workspace_id,
            "content": "Approved 12% discount for Acme",
            "type": "decision",
            "entities": ["Acme"],
        },
    )
    r = api_client.get(
        "/v1/memories/pack_preview",
        params={
            "workspace_id": unique_workspace_id,
            "query": "Acme discount",
            "budget": 500,
            "algorithm": "type_quota",
        },
    )
    assert r.status_code == 200
    pack = r.json()
    assert "memories" in pack
    assert "token_estimate" in pack
    assert "algorithm" in pack
    assert "budget_tokens" in pack


def test_forgetting_run(api_client, unique_workspace_id: str):
    r = api_client.post("/v1/forgetting/run", params={"workspace_id": unique_workspace_id})
    assert r.status_code == 200
    body = r.json()
    assert "events" in body
    assert "count" in body
    assert body["count"] == len(body["events"])


def test_forget_known_memory(api_client, unique_workspace_id: str):
    created = api_client.post(
        "/v1/memories",
        json={
            "workspace_id": unique_workspace_id,
            "content": "Temporary fact to forget",
            "type": "semantic",
        },
    )
    assert created.status_code == 200
    mem_id = created.json()["id"]

    forgotten = api_client.post(
        f"/v1/memories/{mem_id}/forget",
        params={"workspace_id": unique_workspace_id},
    )
    assert forgotten.status_code == 200
    assert forgotten.json()["forgotten"] is True
    assert forgotten.json()["id"] == mem_id

    listed = api_client.get(
        "/v1/memories",
        params={"workspace_id": unique_workspace_id, "status": "forgotten"},
    )
    assert listed.status_code == 200
    assert any(m["id"] == mem_id for m in listed.json()["memories"])
