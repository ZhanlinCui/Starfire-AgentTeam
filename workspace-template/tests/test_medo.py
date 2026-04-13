"""Tests for workspace-template/builtin_tools/medo.py.

All tests exercise the mock backend (no MEDO_API_KEY required).
"""

import sys
from pathlib import Path

import pytest

# workspace-template/ must be on sys.path for `from builtin_tools.medo import` to
# resolve — all other test modules use importlib; this module uses direct imports.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture(autouse=True)
def clear_medo_env(monkeypatch):
    monkeypatch.delenv("MEDO_API_KEY", raising=False)
    monkeypatch.delenv("MEDO_BASE_URL", raising=False)


class TestCreateMedoApp:
    @pytest.mark.asyncio
    async def test_requires_name(self):
        from builtin_tools.medo import create_medo_app
        result = await create_medo_app.ainvoke({"name": ""})
        assert "error" in result

    @pytest.mark.asyncio
    async def test_rejects_unknown_template(self):
        from builtin_tools.medo import create_medo_app
        result = await create_medo_app.ainvoke({"name": "app", "template": "unknown"})
        assert "error" in result and "template" in result["error"]

    @pytest.mark.asyncio
    async def test_mock_success(self):
        from builtin_tools.medo import create_medo_app
        result = await create_medo_app.ainvoke({"name": "my-app", "template": "chatbot"})
        assert result.get("mock") is True and result.get("status") == "ok"


class TestUpdateMedoApp:
    @pytest.mark.asyncio
    async def test_requires_app_id(self):
        from builtin_tools.medo import update_medo_app
        result = await update_medo_app.ainvoke({"app_id": "", "content": {"title": "x"}})
        assert "error" in result

    @pytest.mark.asyncio
    async def test_requires_non_empty_content(self):
        from builtin_tools.medo import update_medo_app
        result = await update_medo_app.ainvoke({"app_id": "abc", "content": {}})
        assert "error" in result

    @pytest.mark.asyncio
    async def test_mock_success(self):
        from builtin_tools.medo import update_medo_app
        result = await update_medo_app.ainvoke({"app_id": "abc", "content": {"title": "v2"}})
        assert result.get("mock") is True and "abc" in result.get("path", "")


class TestPublishMedoApp:
    @pytest.mark.asyncio
    async def test_requires_app_id(self):
        from builtin_tools.medo import publish_medo_app
        result = await publish_medo_app.ainvoke({"app_id": ""})
        assert "error" in result

    @pytest.mark.asyncio
    async def test_rejects_invalid_environment(self):
        from builtin_tools.medo import publish_medo_app
        result = await publish_medo_app.ainvoke({"app_id": "abc", "environment": "dev"})
        assert "error" in result and "environment" in result["error"]

    @pytest.mark.asyncio
    async def test_mock_success(self):
        from builtin_tools.medo import publish_medo_app
        result = await publish_medo_app.ainvoke({"app_id": "abc"})
        assert result.get("mock") is True and result.get("status") == "ok"
