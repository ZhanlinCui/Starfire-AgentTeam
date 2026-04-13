"""Smoke tests for the Hermes adapter PR-1 shell.

PR 1 delivers the Docker image scaffold (Dockerfile, requirements.txt,
__init__.py) but NOT the HermesAdapter class — that ships in PR 2.

Verifies:
  1. Required files exist under adapters/hermes/
  2. requirements.txt declares openai>=1.0.0 (primary runtime dep)
  3. discover_adapters() skips hermes gracefully — no crash, no Adapter class
  4. "hermes" is absent from the adapter map until PR 2 lands
  5. Other adapters (e.g. langgraph) are unaffected by the skip
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

HERMES_DIR = Path(__file__).parent.parent / "adapters" / "hermes"


# ---------------------------------------------------------------------------
# Fixture: isolate adapter cache and sys.modules per test
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_adapter_cache():
    """Clear the module-level adapter cache and evict hermes from sys.modules
    before each test so loader state is fresh, then restore afterwards."""
    import adapters as pkg

    original_cache = dict(pkg._ADAPTER_CACHE)
    pkg._ADAPTER_CACHE.clear()

    evicted = {k: sys.modules.pop(k) for k in list(sys.modules)
               if k == "adapters.hermes" or k.startswith("adapters.hermes.")}
    yield

    # Restore
    pkg._ADAPTER_CACHE.clear()
    pkg._ADAPTER_CACHE.update(original_cache)
    sys.modules.update(evicted)


# ---------------------------------------------------------------------------
# 1. Directory layout — PR-1 shell must have exactly these three files
# ---------------------------------------------------------------------------

class TestHermesShellLayout:

    def test_directory_exists(self):
        assert HERMES_DIR.is_dir(), "adapters/hermes/ directory is missing"

    def test_dockerfile_present(self):
        assert (HERMES_DIR / "Dockerfile").is_file(), "Dockerfile missing from hermes shell"

    def test_init_py_present(self):
        assert (HERMES_DIR / "__init__.py").is_file(), "__init__.py missing from hermes shell"

    def test_requirements_txt_present(self):
        assert (HERMES_DIR / "requirements.txt").is_file(), "requirements.txt missing"

    def test_adapter_py_absent_in_pr1(self):
        """adapter.py is PR-2 scope — must NOT exist in the PR-1 shell.

        If this test starts failing it means PR 2 has landed; move hermes to
        the full adapter test suite in test_adapters.py and delete this file.
        """
        assert not (HERMES_DIR / "adapter.py").exists(), (
            "adapter.py found — PR 2 appears to have merged. "
            "Graduate to test_adapters.py:TestHermesAdapter."
        )


# ---------------------------------------------------------------------------
# 2. requirements.txt — primary dependency contract
# ---------------------------------------------------------------------------

class TestHermesRequirements:

    def test_openai_version_pin(self):
        text = (HERMES_DIR / "requirements.txt").read_text()
        assert "openai>=1.0.0" in text, (
            "Expected 'openai>=1.0.0' in requirements.txt — "
            "the Hermes adapter relies on the OpenAI-compat client for Nous Portal / OpenRouter."
        )

    def test_no_heavy_framework_deps(self):
        """PR-1 shell must not introduce heavy deps that aren't committed to yet."""
        text = (HERMES_DIR / "requirements.txt").read_text().lower()
        heavy = ["langchain", "crewai", "autogen", "langgraph"]
        found = [dep for dep in heavy if dep in text]
        assert not found, f"Unexpected heavy deps in hermes requirements.txt: {found}"


# ---------------------------------------------------------------------------
# 3. Loader integration — graceful skip while adapter.py is absent
# ---------------------------------------------------------------------------

class TestHermesLoaderGracefulSkip:

    def test_discover_does_not_raise(self):
        """discover_adapters() must complete without raising even if hermes
        __init__.py exports no Adapter class."""
        from adapters import discover_adapters
        result = discover_adapters()
        assert isinstance(result, dict)

    def test_hermes_absent_until_pr2(self):
        """'hermes' must NOT appear in the adapter map while adapter.py is missing."""
        from adapters import discover_adapters
        result = discover_adapters()
        assert "hermes" not in result, (
            "'hermes' is registered before adapter.py exists — "
            "the loader skip logic may be broken."
        )

    def test_other_adapters_unaffected(self):
        """Skipping hermes must not block other adapters from loading.
        langgraph has no heavy optional deps and should always be discoverable."""
        from adapters import discover_adapters
        result = discover_adapters()
        assert "langgraph" in result, (
            "langgraph adapter missing after hermes skip — "
            "loader may have short-circuited on the exception."
        )

    def test_hermes_init_importable_without_error(self):
        """The hermes __init__.py must be importable (no syntax errors, no
        missing-dep crashes) — it just exports nothing useful until PR 2."""
        import importlib
        mod = importlib.import_module("adapters.hermes")
        # No Adapter class yet
        assert not hasattr(mod, "Adapter") or getattr(mod, "Adapter", None) is None
