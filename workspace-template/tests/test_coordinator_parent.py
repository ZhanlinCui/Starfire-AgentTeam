"""Tests for coordinator.py — get_parent_context() function."""

import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from coordinator import get_parent_context


@pytest.mark.asyncio
async def test_get_parent_context_no_env(monkeypatch):
    """Returns empty list when PARENT_ID is not set."""
    monkeypatch.delenv("PARENT_ID", raising=False)
    result = await get_parent_context()
    assert result == []


@pytest.mark.asyncio
async def test_get_parent_context_success(monkeypatch):
    """Fetches shared context files from parent workspace via httpx."""
    monkeypatch.setenv("PARENT_ID", "parent-123")
    monkeypatch.setenv("WORKSPACE_ID", "child-456")
    monkeypatch.setenv("PLATFORM_URL", "http://localhost:8080")

    # Reload module-level constants after env change
    import coordinator
    monkeypatch.setattr(coordinator, "PLATFORM_URL", "http://localhost:8080")
    monkeypatch.setattr(coordinator, "WORKSPACE_ID", "child-456")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [
        {"path": "guidelines.md", "content": "Be concise."},
        {"path": "arch.md", "content": "Use microservices."},
    ]

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("coordinator.httpx.AsyncClient", return_value=mock_client):
        result = await get_parent_context()

    assert len(result) == 2
    assert result[0]["path"] == "guidelines.md"
    assert result[0]["content"] == "Be concise."
    assert result[1]["path"] == "arch.md"

    # Verify the correct URL was called
    mock_client.get.assert_called_once_with(
        "http://localhost:8080/workspaces/parent-123/shared-context",
        headers={"X-Workspace-ID": "child-456"},
    )


@pytest.mark.asyncio
async def test_get_parent_context_failure(monkeypatch):
    """Returns empty list when httpx raises an exception."""
    monkeypatch.setenv("PARENT_ID", "parent-123")
    monkeypatch.setenv("WORKSPACE_ID", "child-456")

    import coordinator
    monkeypatch.setattr(coordinator, "PLATFORM_URL", "http://localhost:8080")
    monkeypatch.setattr(coordinator, "WORKSPACE_ID", "child-456")

    mock_client = AsyncMock()
    mock_client.get.side_effect = Exception("Connection refused")
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("coordinator.httpx.AsyncClient", return_value=mock_client):
        result = await get_parent_context()

    assert result == []
