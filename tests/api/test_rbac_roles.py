from __future__ import annotations

import importlib
import json

import pytest

pytestmark = pytest.mark.api


def _reload_api(monkeypatch, tmp_path, roles: dict):
    monkeypatch.setenv("CONTINUUM_DB_PATH", str(tmp_path / "rbac.db"))
    monkeypatch.setenv("CONTINUUM_API_KEY_ROLES", json.dumps(roles))
    monkeypatch.delenv("CONTINUUM_AUTH_DISABLED", raising=False)
    monkeypatch.delenv("CONTINUUM_API_KEYS", raising=False)
    monkeypatch.delenv("CONTINUUM_API_KEY_MAP", raising=False)

    import continuum_api.main as main_mod

    importlib.reload(main_mod)
    from fastapi.testclient import TestClient

    return main_mod, TestClient(main_mod.app)


def test_rbac_reader_cannot_write_or_forget(tmp_path, monkeypatch):
    roles = {
        "reader-key": {"org": "org_r", "role": "reader"},
        "writer-key": {"org": "org_r", "role": "writer"},
        "admin-key": {"org": "org_r", "role": "admin"},
    }
    main_mod, client = _reload_api(monkeypatch, tmp_path, roles)
    try:
        with client:
            headers_r = {"X-API-Key": "reader-key"}
            headers_w = {"X-API-Key": "writer-key"}
            headers_a = {"X-API-Key": "admin-key"}

            ok = client.get("/v1/memories", params={"workspace_id": "ws"}, headers=headers_r)
            assert ok.status_code == 200

            denied = client.post(
                "/v1/memories",
                json={
                    "workspace_id": "ws",
                    "content": "Approved 10% discount for Acme.",
                    "type": "decision",
                },
                headers=headers_r,
            )
            assert denied.status_code == 403

            created = client.post(
                "/v1/memories",
                json={
                    "workspace_id": "ws",
                    "content": "Approved 10% discount for Acme.",
                    "type": "decision",
                },
                headers=headers_w,
            )
            assert created.status_code == 200
            mem_id = created.json()["id"]

            writer_forget = client.post(
                f"/v1/memories/{mem_id}/forget",
                params={"workspace_id": "ws"},
                headers=headers_w,
            )
            assert writer_forget.status_code == 403

            admin_forget = client.post(
                f"/v1/memories/{mem_id}/forget",
                params={"workspace_id": "ws"},
                headers=headers_a,
            )
            assert admin_forget.status_code == 200
            assert admin_forget.json()["forgotten"] is True

            explain = client.get(
                "/v1/memories/explain",
                params={
                    "memory_id": mem_id,
                    "workspace_id": "ws",
                    "query": "Acme discount",
                },
                headers=headers_r,
            )
            assert explain.status_code == 200
            body = explain.json()
            assert "explanation" in body
            assert "cite_overlap" in body
    finally:
        monkeypatch.setenv("CONTINUUM_AUTH_DISABLED", "1")
        monkeypatch.delenv("CONTINUUM_API_KEY_ROLES", raising=False)
        importlib.reload(main_mod)
