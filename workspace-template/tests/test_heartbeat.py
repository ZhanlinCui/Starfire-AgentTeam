"""Tests for heartbeat.py — HeartbeatLoop tracking and HTTP calls."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from heartbeat import HeartbeatLoop


def test_init():
    """HeartbeatLoop stores platform_url, workspace_id, and zeroes counters."""
    hb = HeartbeatLoop("http://localhost:8080", "ws-123")
    assert hb.platform_url == "http://localhost:8080"
    assert hb.workspace_id == "ws-123"
    assert hb.error_count == 0
    assert hb.request_count == 0
    assert hb.active_tasks == 0
    assert hb.sample_error == ""
    assert hb._task is None


def test_record_success():
    """record_success increments request_count only."""
    hb = HeartbeatLoop("http://localhost:8080", "ws-1")
    hb.record_success()
    hb.record_success()
    assert hb.request_count == 2
    assert hb.error_count == 0


def test_record_error():
    """record_error increments both counts and stores sample error."""
    hb = HeartbeatLoop("http://localhost:8080", "ws-1")
    hb.record_error("timeout")
    assert hb.request_count == 1
    assert hb.error_count == 1
    assert hb.sample_error == "timeout"


def test_error_rate_zero_requests():
    """error_rate is 0.0 when no requests have been recorded."""
    hb = HeartbeatLoop("http://localhost:8080", "ws-1")
    assert hb.error_rate == 0.0


def test_error_rate_calculation():
    """error_rate correctly computes error_count / request_count."""
    hb = HeartbeatLoop("http://localhost:8080", "ws-1")
    hb.record_success()
    hb.record_success()
    hb.record_error("fail")
    hb.record_success()
    # 1 error / 4 requests = 0.25
    assert hb.error_rate == 0.25


def test_error_rate_all_errors():
    """error_rate is 1.0 when all requests are errors."""
    hb = HeartbeatLoop("http://localhost:8080", "ws-1")
    hb.record_error("e1")
    hb.record_error("e2")
    assert hb.error_rate == 1.0


def test_sample_error_updated():
    """sample_error always reflects the most recent error."""
    hb = HeartbeatLoop("http://localhost:8080", "ws-1")
    hb.record_error("first")
    hb.record_error("second")
    assert hb.sample_error == "second"


@pytest.mark.asyncio
async def test_heartbeat_loop_posts():
    """The _loop sends a POST to /registry/heartbeat with the correct payload."""
    hb = HeartbeatLoop("http://platform:8080", "ws-abc")
    hb.record_error("some error")
    hb.active_tasks = 2

    mock_response = MagicMock()
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("heartbeat.httpx.AsyncClient", return_value=mock_client):
        # Run the loop but cancel after one iteration
        async def run_one_iteration():
            task = asyncio.create_task(hb._loop())
            await asyncio.sleep(0.05)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        await run_one_iteration()

    mock_client.post.assert_called_once()
    call_args = mock_client.post.call_args
    assert call_args[0][0] == "http://platform:8080/registry/heartbeat"
    payload = call_args[1]["json"]
    assert payload["workspace_id"] == "ws-abc"
    assert payload["error_rate"] == 1.0  # 1 error / 1 request
    assert payload["sample_error"] == "some error"
    assert payload["active_tasks"] == 2
    assert "uptime_seconds" in payload


@pytest.mark.asyncio
async def test_stop_cancels_task():
    """stop() cancels the running heartbeat task."""
    hb = HeartbeatLoop("http://localhost:8080", "ws-1")

    mock_client = AsyncMock()
    mock_client.post = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("heartbeat.httpx.AsyncClient", return_value=mock_client):
        hb.start()
        assert hb._task is not None
        await asyncio.sleep(0.01)
        await hb.stop()
        assert hb._task.cancelled() or hb._task.done()
