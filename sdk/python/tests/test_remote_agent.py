"""Tests for the starfire_agent Phase 30.8 remote-agent client.

The client is pure HTTP — we mock the network via ``requests_mock``-style
monkey-patching of ``requests.Session.get`` / ``.post`` instead of pulling
in a third-party mock library.
"""
from __future__ import annotations

import stat
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from starfire_agent import RemoteAgentClient, WorkspaceState


# ---------------------------------------------------------------------------
# FakeResponse / FakeSession — minimal stand-ins for requests
# ---------------------------------------------------------------------------


class FakeResponse:
    def __init__(self, status_code: int = 200, json_body: Any = None, text: str = ""):
        self.status_code = status_code
        self._json = json_body
        self.text = text

    def json(self) -> Any:
        return self._json

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(f"HTTP {self.status_code}")


@pytest.fixture
def tmp_token_dir(tmp_path: Path) -> Path:
    return tmp_path / "starfire-token-cache"


@pytest.fixture
def client(tmp_token_dir: Path) -> RemoteAgentClient:
    session = MagicMock()
    return RemoteAgentClient(
        workspace_id="ws-abc-123",
        platform_url="http://platform.test",
        agent_card={"name": "test-agent"},
        token_dir=tmp_token_dir,
        session=session,
    )


# ---------------------------------------------------------------------------
# Token persistence
# ---------------------------------------------------------------------------


def test_save_and_load_token_roundtrip(client: RemoteAgentClient, tmp_token_dir: Path):
    client.save_token("secret-token-abc")
    assert client.token_file.exists()
    # File must be 0600 so other local users can't read the credential.
    mode = stat.S_IMODE(client.token_file.stat().st_mode)
    assert mode == 0o600, f"expected 0600, got 0o{mode:o}"
    assert client.load_token() == "secret-token-abc"


def test_save_empty_token_rejected(client: RemoteAgentClient):
    with pytest.raises(ValueError):
        client.save_token("")
    with pytest.raises(ValueError):
        client.save_token("   ")


def test_load_token_returns_none_when_absent(client: RemoteAgentClient):
    assert client.load_token() is None


def test_load_token_returns_none_when_file_empty(client: RemoteAgentClient, tmp_token_dir: Path):
    tmp_token_dir.mkdir(parents=True, exist_ok=True)
    (tmp_token_dir / ".auth_token").write_text("")
    assert client.load_token() is None


def test_token_dir_default_is_under_home(tmp_path: Path):
    # Just verifies the default path shape — we don't want to actually
    # write to $HOME during tests.
    c = RemoteAgentClient(
        workspace_id="ws-xyz",
        platform_url="http://p",
    )
    assert "ws-xyz" in str(c.token_file)
    assert ".starfire" in str(c.token_file)


# ---------------------------------------------------------------------------
# register()
# ---------------------------------------------------------------------------


def test_register_saves_token_when_issued(client: RemoteAgentClient):
    client._session.post.return_value = FakeResponse(
        200, {"status": "registered", "auth_token": "fresh-token-xyz"}
    )

    tok = client.register()

    assert tok == "fresh-token-xyz"
    assert client.load_token() == "fresh-token-xyz"
    # Verify call shape
    url, kwargs = client._session.post.call_args[0][0], client._session.post.call_args[1]
    assert url == "http://platform.test/registry/register"
    assert kwargs["json"]["id"] == "ws-abc-123"
    assert kwargs["json"]["agent_card"] == {"name": "test-agent"}


def test_register_keeps_cached_token_when_platform_omits(client: RemoteAgentClient):
    # Simulate re-register of an already-tokened workspace: platform returns
    # no auth_token, SDK must keep using the cached one.
    client.save_token("cached-from-earlier")
    client._session.post.return_value = FakeResponse(200, {"status": "registered"})

    tok = client.register()
    assert tok == "cached-from-earlier"


def test_register_http_error_propagates(client: RemoteAgentClient):
    client._session.post.return_value = FakeResponse(500, {"error": "boom"})
    with pytest.raises(Exception):
        client.register()


# ---------------------------------------------------------------------------
# pull_secrets()
# ---------------------------------------------------------------------------


def test_pull_secrets_sends_bearer_token(client: RemoteAgentClient):
    client.save_token("tok-for-secrets")
    client._session.get.return_value = FakeResponse(200, {"API_KEY": "v1", "DB_URL": "v2"})

    out = client.pull_secrets()

    assert out == {"API_KEY": "v1", "DB_URL": "v2"}
    url, kwargs = client._session.get.call_args[0][0], client._session.get.call_args[1]
    assert url == "http://platform.test/workspaces/ws-abc-123/secrets/values"
    assert kwargs["headers"]["Authorization"] == "Bearer tok-for-secrets"


def test_pull_secrets_empty_body_yields_empty_dict(client: RemoteAgentClient):
    client.save_token("t")
    client._session.get.return_value = FakeResponse(200, None)
    assert client.pull_secrets() == {}


def test_pull_secrets_401_raises(client: RemoteAgentClient):
    client.save_token("t")
    client._session.get.return_value = FakeResponse(401, {"error": "missing token"})
    with pytest.raises(Exception):
        client.pull_secrets()


# ---------------------------------------------------------------------------
# poll_state()
# ---------------------------------------------------------------------------


def test_poll_state_returns_normal_state(client: RemoteAgentClient):
    client.save_token("t")
    client._session.get.return_value = FakeResponse(
        200, {"workspace_id": "ws-abc-123", "status": "online", "paused": False, "deleted": False}
    )

    state = client.poll_state()

    assert state is not None
    assert state.status == "online"
    assert state.paused is False
    assert state.deleted is False
    assert state.should_stop is False


def test_poll_state_detects_paused(client: RemoteAgentClient):
    client.save_token("t")
    client._session.get.return_value = FakeResponse(
        200, {"workspace_id": "ws-abc-123", "status": "paused", "paused": True, "deleted": False}
    )
    state = client.poll_state()
    assert state.should_stop is True


def test_poll_state_404_means_deleted(client: RemoteAgentClient):
    client.save_token("t")
    client._session.get.return_value = FakeResponse(404, {"deleted": True})

    state = client.poll_state()

    assert state is not None
    assert state.deleted is True
    assert state.should_stop is True


def test_poll_state_server_error_raises(client: RemoteAgentClient):
    client.save_token("t")
    client._session.get.return_value = FakeResponse(500, {"error": "boom"})
    with pytest.raises(Exception):
        client.poll_state()


# ---------------------------------------------------------------------------
# heartbeat()
# ---------------------------------------------------------------------------


def test_heartbeat_sends_full_payload(client: RemoteAgentClient):
    client.save_token("t")
    client._session.post.return_value = FakeResponse(200, {"status": "ok"})

    client.heartbeat(current_task="indexing", active_tasks=1, error_rate=0.1, sample_error="err")

    url = client._session.post.call_args[0][0]
    kwargs = client._session.post.call_args[1]
    assert url == "http://platform.test/registry/heartbeat"
    body = kwargs["json"]
    assert body["workspace_id"] == "ws-abc-123"
    assert body["current_task"] == "indexing"
    assert body["active_tasks"] == 1
    assert body["error_rate"] == 0.1
    assert body["sample_error"] == "err"
    assert "uptime_seconds" in body
    assert kwargs["headers"]["Authorization"] == "Bearer t"


# ---------------------------------------------------------------------------
# run_heartbeat_loop()
# ---------------------------------------------------------------------------


def test_run_loop_exits_on_max_iterations(client: RemoteAgentClient, monkeypatch):
    # Stub sleep so the test doesn't actually wait
    import starfire_agent.client as mod
    monkeypatch.setattr(mod.time, "sleep", lambda s: None)

    client.save_token("t")
    client._session.post.return_value = FakeResponse(200, {"status": "ok"})
    client._session.get.return_value = FakeResponse(
        200, {"status": "online", "paused": False, "deleted": False}
    )

    terminal = client.run_heartbeat_loop(max_iterations=3)

    assert terminal == "max_iterations"
    # 3 heartbeats + 3 state polls
    assert client._session.post.call_count == 3
    assert client._session.get.call_count == 3


def test_run_loop_exits_on_paused(client: RemoteAgentClient, monkeypatch):
    import starfire_agent.client as mod
    monkeypatch.setattr(mod.time, "sleep", lambda s: None)

    client.save_token("t")
    client._session.post.return_value = FakeResponse(200, {"status": "ok"})
    # First iteration: online. Second: paused.
    responses = [
        FakeResponse(200, {"status": "online", "paused": False, "deleted": False}),
        FakeResponse(200, {"status": "paused", "paused": True, "deleted": False}),
    ]
    client._session.get.side_effect = responses

    terminal = client.run_heartbeat_loop(max_iterations=10)

    assert terminal == "paused"
    assert client._session.post.call_count == 2
    assert client._session.get.call_count == 2


def test_run_loop_exits_on_deleted_404(client: RemoteAgentClient, monkeypatch):
    import starfire_agent.client as mod
    monkeypatch.setattr(mod.time, "sleep", lambda s: None)

    client.save_token("t")
    client._session.post.return_value = FakeResponse(200, {"status": "ok"})
    client._session.get.return_value = FakeResponse(404, {"deleted": True})

    terminal = client.run_heartbeat_loop(max_iterations=10)

    assert terminal == "removed"
    assert client._session.get.call_count == 1


def test_run_loop_continues_through_transient_errors(client: RemoteAgentClient, monkeypatch):
    """Network hiccups must log-and-continue, never crash the loop."""
    import starfire_agent.client as mod
    monkeypatch.setattr(mod.time, "sleep", lambda s: None)

    client.save_token("t")

    # Heartbeat fails on iter 1, succeeds on iter 2
    client._session.post.side_effect = [
        ConnectionError("flaky net"),
        FakeResponse(200, {"status": "ok"}),
    ]
    # State poll returns online both times
    client._session.get.return_value = FakeResponse(
        200, {"status": "online", "paused": False, "deleted": False}
    )

    terminal = client.run_heartbeat_loop(max_iterations=2)
    assert terminal == "max_iterations"
    # Both iterations completed despite the first post failing
    assert client._session.post.call_count == 2


def test_run_loop_task_supplier_reported(client: RemoteAgentClient, monkeypatch):
    import starfire_agent.client as mod
    monkeypatch.setattr(mod.time, "sleep", lambda s: None)

    client.save_token("t")
    client._session.post.return_value = FakeResponse(200, {"status": "ok"})
    client._session.get.return_value = FakeResponse(
        200, {"status": "online", "paused": False, "deleted": False}
    )

    reports = [{"current_task": "step-1", "active_tasks": 1}]

    client.run_heartbeat_loop(max_iterations=1, task_supplier=lambda: reports[0])

    body = client._session.post.call_args[1]["json"]
    assert body["current_task"] == "step-1"
    assert body["active_tasks"] == 1


# ---------------------------------------------------------------------------
# WorkspaceState dataclass
# ---------------------------------------------------------------------------


def test_workspace_state_should_stop_semantics():
    assert WorkspaceState("w", "online", False, False).should_stop is False
    assert WorkspaceState("w", "degraded", False, False).should_stop is False
    assert WorkspaceState("w", "paused", True, False).should_stop is True
    assert WorkspaceState("w", "removed", False, True).should_stop is True
