"""Shared fixtures and module mocks for workspace-template tests.

Mocks the a2a SDK modules before any test imports a2a_executor,
since the a2a SDK is a heavy external dependency.
"""

import sys
from types import ModuleType
from unittest.mock import MagicMock


def _make_a2a_mocks():
    """Create mock modules for the a2a SDK with real base classes."""

    # a2a.server.agent_execution needs a real AgentExecutor base class
    agent_execution_mod = ModuleType("a2a.server.agent_execution")

    class AgentExecutor:
        """Stub base class for LangGraphA2AExecutor."""
        pass

    class RequestContext:
        """Stub for type hints."""
        pass

    agent_execution_mod.AgentExecutor = AgentExecutor
    agent_execution_mod.RequestContext = RequestContext

    # a2a.server.events needs a real EventQueue reference
    events_mod = ModuleType("a2a.server.events")

    class EventQueue:
        """Stub for type hints."""
        pass

    events_mod.EventQueue = EventQueue

    # a2a.utils needs new_agent_text_message as a passthrough
    utils_mod = ModuleType("a2a.utils")
    utils_mod.new_agent_text_message = lambda x: x

    # Register all module paths
    a2a_mod = ModuleType("a2a")
    a2a_server_mod = ModuleType("a2a.server")

    sys.modules["a2a"] = a2a_mod
    sys.modules["a2a.server"] = a2a_server_mod
    sys.modules["a2a.server.agent_execution"] = agent_execution_mod
    sys.modules["a2a.server.events"] = events_mod
    sys.modules["a2a.utils"] = utils_mod


def _make_langchain_mocks():
    """Create mock modules for langchain_core so coordinator.py can be imported."""
    langchain_core_mod = ModuleType("langchain_core")
    langchain_core_tools_mod = ModuleType("langchain_core.tools")
    # Make @tool a no-op decorator
    langchain_core_tools_mod.tool = lambda f: f

    sys.modules["langchain_core"] = langchain_core_mod
    sys.modules["langchain_core.tools"] = langchain_core_tools_mod


def _make_tools_mocks():
    """Create mock modules for tools.delegation so coordinator.py can be imported."""
    tools_mod = ModuleType("tools")
    tools_delegation_mod = ModuleType("tools.delegation")
    tools_delegation_mod.delegate_to_workspace = MagicMock()

    sys.modules["tools"] = tools_mod
    sys.modules["tools.delegation"] = tools_delegation_mod


# Install mocks before any test collection imports a2a_executor
if "a2a" not in sys.modules:
    _make_a2a_mocks()

if "langchain_core" not in sys.modules:
    _make_langchain_mocks()

if "tools" not in sys.modules:
    _make_tools_mocks()
