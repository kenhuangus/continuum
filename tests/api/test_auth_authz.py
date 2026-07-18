from __future__ import annotations

import importlib
import os

import pytest

pytestmark = pytest.mark.api


def test_auth_401_without_key_when_enabled(tmp_path, monkeypatch):
    monkeypatch.setenv("CONTINUUM_DB_PATH", str(tmp_path / "auth.db"))
    monkeypatch.setenv("CONTINUUM_API_KEYS", "secret-test-key")
    monkeypatch.delenv("CONTINUUM_AUTH_DISABLED", raising=False)

    import continuum_api.main as main_mod

    importlib.reload(main_mod)
    from fastapi.testclient import TestClient

    with TestClient(main_mod.app) as client:
        assert client.get("/v1/health").status_code == 200
        r = client.get("/v1/memories", params={"workspace_id": "ws"})
        assert r.status_code == 401

        ok = client.get(
            "/v1/memories",
            params={"workspace_id": "ws"},
            headers={"X-API-Key": "secret-test-key"},
        )
        assert ok.status_code == 200

        bearer = client.get(
            "/v1/memories",
            params={"workspace_id": "ws"},
            headers={"Authorization": "Bearer secret-test-key"},
        )
        assert bearer.status_code == 200

    # Restore demo auth-off for other tests
    monkeypatch.setenv("CONTINUUM_AUTH_DISABLED", "1")
    monkeypatch.delenv("CONTINUUM_API_KEYS", raising=False)
    importlib.reload(main_mod)


def test_forget_idor_wrong_workspace(api_client, unique_workspace_id: str):
    created = api_client.post(
        "/v1/memories",
        json={
            "workspace_id": unique_workspace_id,
            "content": "Scoped secret memory",
            "type": "semantic",
        },
    )
    assert created.status_code == 200
    mem_id = created.json()["id"]

    wrong = api_client.post(
        f"/v1/memories/{mem_id}/forget",
        params={"workspace_id": "someone-elses-workspace"},
    )
    assert wrong.status_code == 404

    right = api_client.post(
        f"/v1/memories/{mem_id}/forget",
        params={"workspace_id": unique_workspace_id},
    )
    assert right.status_code == 200
    assert right.json()["forgotten"] is True


def test_request_id_echoed(api_client):
    r = api_client.get("/v1/health", headers={"X-Request-Id": "req-abc-123"})
    assert r.headers.get("X-Request-Id") == "req-abc-123"
