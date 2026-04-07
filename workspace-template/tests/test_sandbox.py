"""Tests for the sandbox run_code tool — subprocess, docker-routing, and e2b backends.

The e2b backend tests use a fully mocked e2b_code_interpreter to avoid
requiring a real E2B_API_KEY or network access in CI.

Design notes:
- sandbox.py lives in tools/ alongside other tool modules.
- conftest.py stubs sys.modules["tools"] so a plain `import tools.sandbox`
  would hit the stub. We load sandbox.py via its file path instead.
- SANDBOX_BACKEND is captured as a module-level constant on load, so
  _load_sandbox() must be called with it set.
- E2B_API_KEY and e2b_code_interpreter are read at call-time inside
  _run_e2b(), so they must be present in os.environ / sys.modules during
  the actual async call (use monkeypatch or patch.dict).
"""

import asyncio
import importlib.util
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
_SANDBOX_PATH = Path(__file__).parent.parent / "tools" / "sandbox.py"


def _load_sandbox(sandbox_backend: str = "subprocess", extra_env: dict | None = None):
    """
    Load (or reload) tools/sandbox.py from its real file path.
    Only SANDBOX_BACKEND needs to be set at load time — it's a module-level
    constant. Other env vars (E2B_API_KEY etc.) are read at call-time and
    should be set by the caller via monkeypatch or patch.dict.
    """
    # Evict any previously cached copy.
    for key in list(sys.modules.keys()):
        if "sandbox_mod" in key:
            del sys.modules[key]

    saved = os.environ.get("SANDBOX_BACKEND")
    os.environ["SANDBOX_BACKEND"] = sandbox_backend

    for k, v in (extra_env or {}).items():
        os.environ[k] = v
    try:
        spec = importlib.util.spec_from_file_location("sandbox_mod", _SANDBOX_PATH)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    finally:
        if saved is None:
            os.environ.pop("SANDBOX_BACKEND", None)
        else:
            os.environ["SANDBOX_BACKEND"] = saved
        for k in (extra_env or {}):
            os.environ.pop(k, None)

    return mod


def _make_e2b_mock(stdout_text: str = "hello e2b\n", stderr_text: str = ""):
    """Build a mock e2b Sandbox that returns a plausible execution result."""
    result_obj = MagicMock()
    result_obj.text = stdout_text
    result_obj.error = None

    logs_obj = MagicMock()
    logs_obj.stdout = []
    logs_obj.stderr = [stderr_text] if stderr_text else []

    exec_obj = MagicMock()
    exec_obj.results = [result_obj]
    exec_obj.logs = logs_obj

    sandbox_instance = MagicMock()
    sandbox_instance.run_code.return_value = exec_obj
    sandbox_instance.kill.return_value = None

    sandbox_cls = MagicMock(return_value=sandbox_instance)
    return sandbox_cls, sandbox_instance


def _run_sync(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# subprocess backend
# ---------------------------------------------------------------------------

class TestSubprocessBackend:
    def test_python_hello(self):
        sb = _load_sandbox("subprocess")
        result = _run_sync(sb._run_subprocess('print("hello subprocess")', "python"))
        assert result["exit_code"] == 0
        assert "hello subprocess" in result["stdout"]
        assert result["backend"] == "subprocess"

    def test_stderr_nonzero_exit(self):
        sb = _load_sandbox("subprocess")
        result = _run_sync(sb._run_subprocess("import sys; sys.exit(2)", "python"))
        assert result["exit_code"] == 2

    def test_unsupported_language(self):
        sb = _load_sandbox("subprocess")
        result = _run_sync(sb._run_subprocess("code", "cobol"))
        assert result["exit_code"] == -1
        assert "Unsupported" in result["error"]

    def test_syntax_error_captured_in_stderr(self):
        sb = _load_sandbox("subprocess")
        result = _run_sync(sb._run_subprocess("def broken(:", "python"))
        assert result["exit_code"] != 0

    def test_timeout(self):
        sb = _load_sandbox("subprocess", {"SANDBOX_TIMEOUT": "1"})
        # Manually set the module-level constant that was captured at load time
        sb.SANDBOX_TIMEOUT = 1
        result = _run_sync(sb._run_subprocess("import time; time.sleep(10)", "python"))
        assert result["exit_code"] == -1
        assert "Timeout" in result["error"]


# ---------------------------------------------------------------------------
# E2B backend
# ---------------------------------------------------------------------------

class TestE2BBackend:
    """
    All tests mock e2b_code_interpreter to avoid real network calls.
    E2B_API_KEY must be present in os.environ for the duration of _run_e2b
    (it's read at call-time, not module-load time).
    """

    def _call_e2b(self, code: str, language: str, sandbox_cls, api_key: str = "test-key"):
        sb = _load_sandbox("e2b")
        mock_mod = MagicMock()
        mock_mod.Sandbox = sandbox_cls
        with patch.dict(os.environ, {"E2B_API_KEY": api_key}):
            with patch.dict("sys.modules", {"e2b_code_interpreter": mock_mod}):
                return _run_sync(sb._run_e2b(code, language)), sb, sandbox_cls

    def test_python_success(self):
        sandbox_cls, sandbox_instance = _make_e2b_mock(stdout_text="42\n")
        result, _, _ = self._call_e2b("print(6 * 7)", "python", sandbox_cls)

        assert result["exit_code"] == 0
        assert result["backend"] == "e2b"
        assert result["language"] == "python"
        assert result["stdout"] == "42\n"
        sandbox_instance.kill.assert_called_once()

    def test_javascript_success(self):
        sandbox_cls, sandbox_instance = _make_e2b_mock(stdout_text="hello js\n")
        result, _, _ = self._call_e2b('console.log("hi")', "javascript", sandbox_cls)

        assert result["exit_code"] == 0
        assert result["language"] == "javascript"
        # E2B kernel must be remapped: "javascript" → "js"
        call_args = sandbox_instance.run_code.call_args
        called_kernel = (
            call_args.kwargs.get("language")
            or (call_args.args[1] if len(call_args.args) > 1 else None)
        )
        assert called_kernel == "js", f"Expected kernel 'js', got {called_kernel!r}"

    def test_stderr_produces_nonzero_exit(self):
        sandbox_cls, _ = _make_e2b_mock(
            stdout_text="", stderr_text="NameError: name 'x' is not defined"
        )
        result, _, _ = self._call_e2b("print(x)", "python", sandbox_cls)

        assert result["exit_code"] == 1
        assert "NameError" in result["stderr"]

    def test_missing_api_key_returns_error(self):
        sb = _load_sandbox("e2b")
        sandbox_cls, _ = _make_e2b_mock()
        mock_mod = MagicMock()
        mock_mod.Sandbox = sandbox_cls
        # Do NOT set E2B_API_KEY
        with patch.dict("sys.modules", {"e2b_code_interpreter": mock_mod}):
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("E2B_API_KEY", None)
                result = _run_sync(sb._run_e2b("print(1)", "python"))

        assert result["exit_code"] == -1
        assert "E2B_API_KEY" in result["error"]

    def test_missing_package_returns_error(self):
        sb = _load_sandbox("e2b")
        with patch.dict(os.environ, {"E2B_API_KEY": "key"}):
            # Simulate ImportError by putting None in sys.modules
            with patch.dict("sys.modules", {"e2b_code_interpreter": None}):
                result = _run_sync(sb._run_e2b("print(1)", "python"))

        assert result["exit_code"] == -1
        assert "e2b-code-interpreter" in result["error"]

    def test_unsupported_language_returns_error(self):
        sandbox_cls, _ = _make_e2b_mock()
        result, _, _ = self._call_e2b("echo hi", "shell", sandbox_cls)

        assert result["exit_code"] == -1
        assert "not supported by the e2b backend" in result["error"]

    def test_sandbox_always_killed_on_exception(self):
        """sandbox.kill() is called even when run_code raises."""
        sandbox_instance = MagicMock()
        sandbox_instance.run_code.side_effect = RuntimeError("network error")
        sandbox_instance.kill.return_value = None
        sandbox_cls = MagicMock(return_value=sandbox_instance)

        result, _, _ = self._call_e2b("print(1)", "python", sandbox_cls)

        assert result["exit_code"] == -1
        assert "network error" in result["error"]
        sandbox_instance.kill.assert_called_once()

    def test_output_truncated_at_max_output(self):
        big = "x" * 20_000
        sandbox_cls, _ = _make_e2b_mock(stdout_text=big)
        result, sb, _ = self._call_e2b("print('x' * 20000)", "python", sandbox_cls)

        assert "stdout" in result
        assert len(result["stdout"]) <= sb.MAX_OUTPUT

    def test_api_key_forwarded_to_constructor(self):
        """E2B_API_KEY from env is passed to Sandbox(api_key=...)."""
        sandbox_cls, _ = _make_e2b_mock()
        _, _, used_cls = self._call_e2b("print(1)", "python", sandbox_cls, api_key="my-secret")

        call_kwargs = used_cls.call_args.kwargs
        assert call_kwargs.get("api_key") == "my-secret"

    def test_timeout_forwarded_to_constructor(self):
        """SANDBOX_TIMEOUT is forwarded as the sandbox timeout kwarg."""
        sandbox_cls, _ = _make_e2b_mock()
        sb = _load_sandbox("e2b", {"SANDBOX_TIMEOUT": "45"})
        sb.SANDBOX_TIMEOUT = 45

        mock_mod = MagicMock()
        mock_mod.Sandbox = sandbox_cls
        with patch.dict(os.environ, {"E2B_API_KEY": "key"}):
            with patch.dict("sys.modules", {"e2b_code_interpreter": mock_mod}):
                _run_sync(sb._run_e2b("print(1)", "python"))

        call_kwargs = sandbox_cls.call_args.kwargs
        assert call_kwargs.get("timeout") == 45


# ---------------------------------------------------------------------------
# Dispatcher routing — verify SANDBOX_BACKEND selects the right function
# ---------------------------------------------------------------------------

class TestRunCodeDispatcher:
    def test_subprocess_backend_dispatched(self):
        sb = _load_sandbox("subprocess")
        assert sb.SANDBOX_BACKEND == "subprocess"
        result = _run_sync(sb._run_subprocess("1 + 1", "python"))
        assert result["exit_code"] == 0

    def test_e2b_backend_dispatched(self):
        """run_code routes to _run_e2b when SANDBOX_BACKEND=e2b."""
        sb = _load_sandbox("e2b")
        assert sb.SANDBOX_BACKEND == "e2b"

        called_with = []

        async def fake_e2b(code, language):
            called_with.append((code, language))
            return {"exit_code": 0, "stdout": "ok", "backend": "e2b"}

        with patch.object(sb, "_run_e2b", fake_e2b):
            # conftest mocks @tool as identity, so run_code is the raw async fn
            result = _run_sync(sb.run_code("print(1)", "python"))

        assert called_with == [("print(1)", "python")]
        assert result["backend"] == "e2b"

    def test_docker_backend_dispatched(self):
        """run_code routes to _run_docker when SANDBOX_BACKEND=docker."""
        sb = _load_sandbox("docker")
        assert sb.SANDBOX_BACKEND == "docker"

        called_with = []

        async def fake_docker(code, language):
            called_with.append((code, language))
            return {"exit_code": 0, "stdout": "ok", "backend": "docker"}

        with patch.object(sb, "_run_docker", fake_docker):
            result = _run_sync(sb.run_code("echo hi", "shell"))

        assert called_with == [("echo hi", "shell")]
        assert result["backend"] == "docker"
