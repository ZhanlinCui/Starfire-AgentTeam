"""Tests for workspace memory tools and awareness routing."""

import asyncio
import json
import importlib.util
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = ROOT / "tools"


def _load_module(module_name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def memory_modules(monkeypatch):
    """Load the tools package modules from disk for focused unit tests."""
    monkeypatch.setenv("PLATFORM_URL", "http://platform.test")
    monkeypatch.setenv("WORKSPACE_ID", "ws-test")
    monkeypatch.delenv("AWARENESS_URL", raising=False)
    monkeypatch.delenv("AWARENESS_NAMESPACE", raising=False)

    tools_pkg = sys.modules.get("tools")
    original_tools_memory = sys.modules.pop("tools.memory", None)
    original_tools_awareness = sys.modules.pop("tools.awareness_client", None)

    if tools_pkg is not None:
        monkeypatch.setattr(tools_pkg, "__path__", [str(TOOLS_DIR)], raising=False)

    awareness_client = _load_module("tools.awareness_client", TOOLS_DIR / "awareness_client.py")
    memory = _load_module("tools.memory", TOOLS_DIR / "memory.py")

    yield memory, awareness_client

    if original_tools_memory is not None:
        sys.modules["tools.memory"] = original_tools_memory
    else:
        sys.modules.pop("tools.memory", None)

    if original_tools_awareness is not None:
        sys.modules["tools.awareness_client"] = original_tools_awareness
    else:
        sys.modules.pop("tools.awareness_client", None)


class _FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
        self.text = str(payload)

    def json(self):
        return self._payload


def test_commit_memory_uses_awareness_client_when_configured(monkeypatch, memory_modules):
    memory, _awareness_client = memory_modules
    captured = {}

    class FakeAsyncClient:
        def __init__(self, timeout):
            captured["timeout"] = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, json):
            captured["url"] = url
            captured["json"] = json
            return _FakeResponse(201, {"id": "mem-123"})

    monkeypatch.setenv("AWARENESS_URL", "http://awareness.test")
    monkeypatch.setenv("AWARENESS_NAMESPACE", "ws-test")
    monkeypatch.setattr(memory.httpx, "AsyncClient", FakeAsyncClient)

    result = asyncio.run(memory.commit_memory("remember this", "team"))

    assert result == {"success": True, "id": "mem-123", "scope": "TEAM"}
    assert captured["url"] == "http://awareness.test/api/v1/namespaces/ws-test/memories"
    assert captured["json"] == {"content": "remember this", "scope": "TEAM"}


def test_search_memory_uses_platform_fallback_without_awareness(monkeypatch, memory_modules):
    memory, _awareness_client = memory_modules
    captured = {}

    class FakeAsyncClient:
        def __init__(self, timeout):
            captured["timeout"] = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def get(self, url, params):
            captured["url"] = url
            captured["params"] = params
            return _FakeResponse(200, [{"content": "existing"}])

    monkeypatch.setattr(memory.httpx, "AsyncClient", FakeAsyncClient)

    result = asyncio.run(memory.search_memory("status", "local"))

    assert result == {
        "success": True,
        "count": 1,
        "memories": [{"content": "existing"}],
    }
    assert captured["url"] == "http://platform.test/workspaces/ws-test/memories"
    assert captured["params"] == {"q": "status", "scope": "LOCAL"}


def test_commit_memory_uses_platform_fallback_without_awareness(monkeypatch, memory_modules):
    memory, _awareness_client = memory_modules
    captured = {}

    class FakeAsyncClient:
        def __init__(self, timeout):
            captured["timeout"] = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, json):
            captured["url"] = url
            captured["json"] = json
            return _FakeResponse(201, {"id": "platform-mem"})

    monkeypatch.setattr(memory.httpx, "AsyncClient", FakeAsyncClient)

    result = asyncio.run(memory.commit_memory("remember fallback", "global"))

    assert result == {"success": True, "id": "platform-mem", "scope": "GLOBAL"}
    assert captured["url"] == "http://platform.test/workspaces/ws-test/memories"
    assert captured["json"] == {"content": "remember fallback", "scope": "GLOBAL"}


def test_commit_memory_promoted_packet_logs_skill_promotion(monkeypatch, tmp_path, memory_modules):
    memory, _awareness_client = memory_modules
    captured = {"calls": []}

    class FakeAsyncClient:
        def __init__(self, timeout):
            captured.setdefault("timeouts", []).append(timeout)

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, json):
            captured["calls"].append((url, json))
            if url.endswith("/memories"):
                return _FakeResponse(201, {"id": "mem-skill"})
            if url.endswith("/activity"):
                return _FakeResponse(200, {"status": "logged"})
            raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr(memory.httpx, "AsyncClient", FakeAsyncClient)

    packet = {
        "title": "Normalize webhook ingress",
        "summary": "Repeated GitHub webhook handling is now a skill candidate",
        "promote_to_skill": True,
        "repetition_signal": {
            "count": 2,
            "workflow": "github webhook ingress",
        },
        "what changed": "The same webhook normalization was done twice cleanly.",
        "why it matters": "It is now stable enough to promote into SKILL.md.",
    }

    result = asyncio.run(memory.commit_memory(json.dumps(packet), "team"))

    assert result == {"success": True, "id": "mem-skill", "scope": "TEAM"}
    assert len(captured["calls"]) == 3
    memory_url, memory_payload = captured["calls"][0]
    activity_url, activity_payload = captured["calls"][1]
    heartbeat_url, heartbeat_payload = captured["calls"][2]
    assert memory_url == "http://platform.test/workspaces/ws-test/memories"
    assert memory_payload == {"content": json.dumps(packet), "scope": "TEAM"}
    assert activity_url == "http://platform.test/workspaces/ws-test/activity"
    assert activity_payload["activity_type"] == "skill_promotion"
    assert activity_payload["method"] == "memory/skill-promotion"
    assert activity_payload["summary"] == "Repeated GitHub webhook handling is now a skill candidate"
    assert activity_payload["metadata"]["promote_to_skill"] is True
    assert activity_payload["metadata"]["memory_id"] == "mem-skill"
    assert activity_payload["metadata"]["repetition_signal"] == packet["repetition_signal"]
    assert heartbeat_url == "http://platform.test/registry/heartbeat"
    assert heartbeat_payload["current_task"] == "Skill promotion: Repeated GitHub webhook handling is now a skill candidate"
    assert heartbeat_payload["active_tasks"] == 1

    assert not (tmp_path / "skills").exists()


def test_search_memory_rejects_invalid_scope(memory_modules):
    memory, _awareness_client = memory_modules

    result = asyncio.run(memory.search_memory("status", "bad"))

    assert result == {"error": "scope must be LOCAL, TEAM, GLOBAL, or empty"}
