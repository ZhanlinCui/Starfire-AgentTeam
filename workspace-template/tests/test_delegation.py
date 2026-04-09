import os
"""Tests for tools/delegation.py.

Loads the real module via importlib to bypass the conftest.py mock at
sys.modules["tools.delegation"].  All dependency mocks (tools.audit,
tools.telemetry, httpx.AsyncClient) are applied before the module is
exec'd so every import-time name binding picks up the fakes.
"""

import importlib.util
import sys
from unittest.mock import AsyncMock, MagicMock, patch, call

import httpx
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_client(
    discover_status=200,
    discover_payload=None,
    discover_exc=None,
    a2a_status=200,
    a2a_payload=None,
):
    """Return (mock_client, mock_client_class) for patching httpx.AsyncClient."""
    if discover_payload is None:
        discover_payload = {"url": "http://target:8000"}

    if a2a_payload is None:
        a2a_payload = {
            "result": {
                "artifacts": [
                    {"parts": [{"kind": "text", "text": "done"}]}
                ]
            }
        }

    mock_discover_resp = MagicMock()
    mock_discover_resp.status_code = discover_status
    mock_discover_resp.json = MagicMock(return_value=discover_payload)

    mock_a2a_resp = MagicMock()
    mock_a2a_resp.status_code = a2a_status
    mock_a2a_resp.json = MagicMock(return_value=a2a_payload)

    mock_client = AsyncMock()
    if discover_exc is not None:
        mock_client.get = AsyncMock(side_effect=discover_exc)
    else:
        mock_client.get = AsyncMock(return_value=mock_discover_resp)
    mock_client.post = AsyncMock(return_value=mock_a2a_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    mock_client_cls = MagicMock(return_value=mock_client)
    return mock_client, mock_client_cls


# ---------------------------------------------------------------------------
# Fixture: load the real delegation module with mocked dependencies
# ---------------------------------------------------------------------------

@pytest.fixture
def delegation_mocks(monkeypatch):
    """Load tools/delegation.py against mocked audit and telemetry modules."""

    # ---- tools.audit --------------------------------------------------------
    mock_audit = MagicMock()
    mock_audit.check_permission = MagicMock(return_value=True)
    mock_audit.get_workspace_roles = MagicMock(return_value=(["operator"], {}))
    mock_audit.log_event = MagicMock(return_value="trace-123")
    monkeypatch.setitem(sys.modules, "tools.audit", mock_audit)

    # ---- tools.telemetry ----------------------------------------------------
    mock_span = MagicMock()
    mock_span.__enter__ = MagicMock(return_value=mock_span)
    mock_span.__exit__ = MagicMock(return_value=False)

    mock_tracer = MagicMock()
    mock_tracer.start_as_current_span = MagicMock(return_value=mock_span)

    mock_telemetry = MagicMock()
    mock_telemetry.get_tracer = MagicMock(return_value=mock_tracer)
    mock_telemetry.inject_trace_headers = MagicMock(side_effect=lambda h: h)
    mock_telemetry.get_current_traceparent = MagicMock(return_value=None)
    mock_telemetry.A2A_SOURCE_WORKSPACE = "a2a.source_workspace_id"
    mock_telemetry.A2A_TARGET_WORKSPACE = "a2a.target_workspace_id"
    mock_telemetry.A2A_TASK_ID = "a2a.task_id"
    mock_telemetry.WORKSPACE_ID_ATTR = "workspace.id"
    monkeypatch.setitem(sys.modules, "tools.telemetry", mock_telemetry)

    # ---- Reload delegation module -------------------------------------------
    monkeypatch.delitem(sys.modules, "tools.delegation", raising=False)
    spec = importlib.util.spec_from_file_location(
        "tools.delegation",
        os.path.join(os.path.dirname(__file__), "..", "tools", "delegation.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "tools.delegation", mod)
    spec.loader.exec_module(mod)

    # Speed up retry tests
    mod.DELEGATION_RETRY_ATTEMPTS = 2
    mod.DELEGATION_RETRY_DELAY = 0.0

    return mod, mock_audit, mock_telemetry, mock_span


# ---------------------------------------------------------------------------
# Convenience: call the tool
# ---------------------------------------------------------------------------

async def _invoke(mod, workspace_id="target", task="do stuff"):
    """Call the tool, handling both LangChain tool objects and raw async functions.

    When the conftest.py mock replaces `langchain_core.tools.tool` with a no-op
    decorator the module-level `@tool` has no effect and `delegate_to_workspace`
    is just a plain async function.  When the real langchain_core is installed it
    is a StructuredTool with `.ainvoke()`.
    """
    fn = mod.delegate_to_workspace
    if hasattr(fn, "ainvoke"):
        return await fn.ainvoke({"workspace_id": workspace_id, "task": task})
    # Plain coroutine function (no-op @tool from conftest mock)
    return await fn(workspace_id=workspace_id, task=task)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestRBAC:

    async def test_rbac_deny(self, delegation_mocks):
        mod, mock_audit, *_ = delegation_mocks
        mock_audit.check_permission.return_value = False

        result = await _invoke(mod)

        assert result["success"] is False
        assert "RBAC" in result["error"]
        # Should have logged rbac.deny
        logged_actions = [
            kw.get("action") or (args[1] if len(args) > 1 else None)
            for args, kw in (
                (c.args, c.kwargs) for c in mock_audit.log_event.call_args_list
            )
        ]
        assert any("rbac.deny" in str(a) for a in logged_actions)


class TestDiscovery:

    async def test_discovery_403(self, delegation_mocks):
        mod, mock_audit, *_ = delegation_mocks
        _, mock_cls = _make_mock_client(discover_status=403)

        with patch("httpx.AsyncClient", mock_cls):
            result = await _invoke(mod)

        assert result["success"] is False
        assert "Not authorized" in result["error"]

    async def test_discovery_404(self, delegation_mocks):
        mod, *_ = delegation_mocks
        _, mock_cls = _make_mock_client(discover_status=404)

        with patch("httpx.AsyncClient", mock_cls):
            result = await _invoke(mod)

        assert result["success"] is False
        assert "not found" in result["error"].lower()

    async def test_discovery_non_200(self, delegation_mocks):
        mod, *_ = delegation_mocks
        _, mock_cls = _make_mock_client(discover_status=500)

        with patch("httpx.AsyncClient", mock_cls):
            result = await _invoke(mod)

        assert result["success"] is False
        assert "Discovery failed" in result["error"]

    async def test_discovery_no_url(self, delegation_mocks):
        mod, *_ = delegation_mocks
        _, mock_cls = _make_mock_client(
            discover_status=200,
            discover_payload={"url": None},
        )

        with patch("httpx.AsyncClient", mock_cls):
            result = await _invoke(mod)

        assert result["success"] is False
        assert "has no URL" in result["error"]

    async def test_discovery_exception(self, delegation_mocks):
        mod, *_ = delegation_mocks
        _, mock_cls = _make_mock_client(discover_exc=RuntimeError("DNS failure"))

        with patch("httpx.AsyncClient", mock_cls):
            result = await _invoke(mod)

        assert result["success"] is False
        assert "Discovery error" in result["error"]


class TestA2ASuccess:

    async def test_success_with_artifacts(self, delegation_mocks):
        mod, *_ = delegation_mocks
        payload = {
            "result": {
                "artifacts": [
                    {"parts": [{"kind": "text", "text": "Hello"}, {"kind": "text", "text": "World"}]}
                ]
            }
        }
        _, mock_cls = _make_mock_client(a2a_payload=payload)

        with patch("httpx.AsyncClient", mock_cls):
            result = await _invoke(mod)

        assert result["success"] is True
        assert "Hello" in result["response"]
        assert "World" in result["response"]
        assert result["workspace_id"] == "target"

    async def test_success_no_artifacts(self, delegation_mocks):
        mod, *_ = delegation_mocks
        task_result_obj = {"status": "completed", "artifacts": []}
        payload = {"result": task_result_obj}
        _, mock_cls = _make_mock_client(a2a_payload=payload)

        with patch("httpx.AsyncClient", mock_cls):
            result = await _invoke(mod)

        assert result["success"] is True
        # No text parts → falls back to str(task_result)
        assert str(task_result_obj) in result["response"]


class TestA2AErrors:

    async def test_rpc_error(self, delegation_mocks):
        mod, *_ = delegation_mocks
        payload = {"error": {"message": "RPC error from target"}}
        _, mock_cls = _make_mock_client(a2a_payload=payload)

        with patch("httpx.AsyncClient", mock_cls):
            result = await _invoke(mod)

        assert result["success"] is False
        assert "RPC error from target" in str(result.get("error", ""))

    async def test_network_retry_then_success(self, delegation_mocks):
        mod, *_ = delegation_mocks

        # First POST raises ConnectError; second succeeds.
        success_payload = {
            "result": {
                "artifacts": [{"parts": [{"kind": "text", "text": "ok"}]}]
            }
        }
        mock_success_resp = MagicMock()
        mock_success_resp.status_code = 200
        mock_success_resp.json = MagicMock(return_value=success_payload)

        post_calls = {"n": 0}

        async def fake_post(*args, **kwargs):
            post_calls["n"] += 1
            if post_calls["n"] == 1:
                raise httpx.ConnectError("connection refused")
            return mock_success_resp

        mock_discover_resp = MagicMock()
        mock_discover_resp.status_code = 200
        mock_discover_resp.json = MagicMock(return_value={"url": "http://target:8000"})

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_discover_resp)
        mock_client.post = fake_post
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await _invoke(mod)

        assert result["success"] is True
        assert post_calls["n"] == 2

    async def test_network_retry_exhausted(self, delegation_mocks):
        mod, *_ = delegation_mocks

        mock_discover_resp = MagicMock()
        mock_discover_resp.status_code = 200
        mock_discover_resp.json = MagicMock(return_value={"url": "http://target:8000"})

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_discover_resp)
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await _invoke(mod)

        assert result["success"] is False
        # post called DELEGATION_RETRY_ATTEMPTS times
        assert mock_client.post.call_count == mod.DELEGATION_RETRY_ATTEMPTS


class TestDiscoverySpanRecordExceptionFails:

    async def test_discovery_exception_span_record_exception_fails(self, delegation_mocks):
        """When delegate_span.record_exception raises, exception is swallowed."""
        mod, mock_audit, mock_telemetry, mock_span = delegation_mocks
        # Make record_exception raise
        mock_span.record_exception = MagicMock(side_effect=RuntimeError("span broken"))

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(side_effect=OSError("connection refused"))
            MockClient.return_value = mock_client

            result = await _invoke(mod, workspace_id="target-ws", task="do it")

        assert result["success"] is False


class TestAuditAndOTEL:

    async def test_audit_events_on_success(self, delegation_mocks):
        mod, mock_audit, *_ = delegation_mocks
        _, mock_cls = _make_mock_client()

        with patch("httpx.AsyncClient", mock_cls):
            result = await _invoke(mod)

        assert result["success"] is True
        outcomes = [
            c.kwargs.get("outcome")
            for c in mock_audit.log_event.call_args_list
        ]
        assert "allowed" in outcomes
        assert "success" in outcomes

    async def test_otel_span_attributes_set(self, delegation_mocks):
        mod, _, mock_telemetry, mock_span = delegation_mocks
        _, mock_cls = _make_mock_client()

        with patch("httpx.AsyncClient", mock_cls):
            await _invoke(mod, workspace_id="ws-x")

        # set_attribute should have been called at least for the workspace attrs
        attr_keys = [c.args[0] for c in mock_span.set_attribute.call_args_list]
        assert mock_telemetry.WORKSPACE_ID_ATTR in attr_keys
        assert mock_telemetry.A2A_TARGET_WORKSPACE in attr_keys
        assert mock_telemetry.A2A_TASK_ID in attr_keys
