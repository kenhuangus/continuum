"""Multi-tenant org isolation via CONTINUUM_API_KEY_MAP."""

from __future__ import annotations

import importlib
import json

import pytest

pytestmark = pytest.mark.api


def _reload_api(monkeypatch, tmp_path, key_map: dict[str, str]):
    monkeypatch.setenv("CONTINUUM_DB_PATH", str(tmp_path / "org.db"))
    monkeypatch.setenv("CONTINUUM_API_KEY_MAP", json.dumps(key_map))
    monkeypatch.delenv("CONTINUUM_AUTH_DISABLED", raising=False)
    monkeypatch.delenv("CONTINUUM_API_KEYS", raising=False)

    import continuum_api.main as main_mod

    importlib.reload(main_mod)
    from fastapi.testclient import TestClient

    return TestClient(main_mod.app), main_mod


def test_org_isolation_list_search_get_forget(tmp_path, monkeypatch):
    key_map = {"key-a": "org_a", "key-b": "org_b"}
    client, main_mod = _reload_api(monkeypatch, tmp_path, key_map)
    ws = "shared-ws"

    with client:
        created = client.post(
            "/v1/memories",
            json={
                "workspace_id": ws,
                "org_id": "org_a",
                "content": "Org A secret discount 42%",
                "type": "decision",
            },
            headers={"X-API-Key": "key-a"},
        )
        assert created.status_code == 200
        mem_id = created.json()["id"]
        assert created.json()["org_id"] == "org_a"

        # Same workspace_id, different org → empty list / search
        listed_b = client.get(
            "/v1/memories",
            params={"workspace_id": ws},
            headers={"X-API-Key": "key-b"},
        )
        assert listed_b.status_code == 200
        assert listed_b.json()["memories"] == []

        search_b = client.get(
            "/v1/memories",
            params={"workspace_id": ws, "q": "discount"},
            headers={"X-API-Key": "key-b"},
        )
        assert search_b.status_code == 200
        assert search_b.json()["memories"] == []

        get_b = client.get(
            f"/v1/memories/{mem_id}",
            params={"workspace_id": ws},
            headers={"X-API-Key": "key-b"},
        )
        assert get_b.status_code == 404

        forget_b = client.post(
            f"/v1/memories/{mem_id}/forget",
            params={"workspace_id": ws},
            headers={"X-API-Key": "key-b"},
        )
        assert forget_b.status_code == 404

        # Owner org can still see and forget
        listed_a = client.get(
            "/v1/memories",
            params={"workspace_id": ws},
            headers={"X-API-Key": "key-a"},
        )
        assert listed_a.status_code == 200
        assert len(listed_a.json()["memories"]) == 1

        forget_a = client.post(
            f"/v1/memories/{mem_id}/forget",
            params={"workspace_id": ws},
            headers={"X-API-Key": "key-a"},
        )
        assert forget_a.status_code == 200
        assert forget_a.json()["forgotten"] is True

    monkeypatch.setenv("CONTINUUM_AUTH_DISABLED", "1")
    monkeypatch.delenv("CONTINUUM_API_KEY_MAP", raising=False)
    importlib.reload(main_mod)


def test_org_id_mismatch_returns_403(tmp_path, monkeypatch):
    key_map = {"key-a": "org_a"}
    client, main_mod = _reload_api(monkeypatch, tmp_path, key_map)

    with client:
        bad = client.post(
            "/v1/memories",
            json={
                "workspace_id": "ws",
                "org_id": "org_other",
                "content": "should fail",
                "type": "semantic",
            },
            headers={"X-API-Key": "key-a"},
        )
        assert bad.status_code == 403

    monkeypatch.setenv("CONTINUUM_AUTH_DISABLED", "1")
    monkeypatch.delenv("CONTINUUM_API_KEY_MAP", raising=False)
    importlib.reload(main_mod)
