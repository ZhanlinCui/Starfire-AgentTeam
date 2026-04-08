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
    """Create mock modules for tools.* so adapters can be imported in tests."""
    tools_mod = ModuleType("tools")
    tools_mod.__path__ = []  # Make it a proper package

    tools_delegation_mod = ModuleType("tools.delegation")
    tools_delegation_mod.delegate_to_workspace = MagicMock()
    tools_delegation_mod.delegate_to_workspace.name = "delegate_to_workspace"

    tools_approval_mod = ModuleType("tools.approval")
    tools_approval_mod.request_approval = MagicMock()
    tools_approval_mod.request_approval.name = "request_approval"

    tools_memory_mod = ModuleType("tools.memory")
    tools_memory_mod.commit_memory = MagicMock()
    tools_memory_mod.commit_memory.name = "commit_memory"
    tools_memory_mod.search_memory = MagicMock()
    tools_memory_mod.search_memory.name = "search_memory"

    tools_sandbox_mod = ModuleType("tools.sandbox")
    tools_sandbox_mod.run_code = MagicMock()
    tools_sandbox_mod.run_code.name = "run_code"

    tools_a2a_mod = ModuleType("tools.a2a_tools")
    tools_a2a_mod.delegate_task = MagicMock()
    tools_a2a_mod.list_peers = MagicMock()
    tools_a2a_mod.get_peers_summary = MagicMock()

    tools_awareness_mod = ModuleType("tools.awareness_client")
    tools_awareness_mod.get_awareness_config = MagicMock(return_value=None)

    sys.modules["tools"] = tools_mod
    sys.modules["tools.delegation"] = tools_delegation_mod
    sys.modules["tools.approval"] = tools_approval_mod
    sys.modules["tools.memory"] = tools_memory_mod
    sys.modules["tools.sandbox"] = tools_sandbox_mod
    sys.modules["tools.a2a_tools"] = tools_a2a_mod
    sys.modules["tools.awareness_client"] = tools_awareness_mod


# Install mocks before any test collection imports a2a_executor
if "a2a" not in sys.modules:
    _make_a2a_mocks()

if "langchain_core" not in sys.modules:
    _make_langchain_mocks()

if "tools" not in sys.modules or not hasattr(sys.modules.get("tools"), "__path__"):
    _make_tools_mocks()

# Mock additional modules needed by _common_setup in base.py
if "plugins" not in sys.modules:
    plugins_mod = ModuleType("plugins")
    plugins_mod.load_plugins = MagicMock()
    sys.modules["plugins"] = plugins_mod

if "skills" not in sys.modules:
    # Add workspace-template to path so real skills.loader can be imported
    import importlib.util
    _ws_root = str(MagicMock.__module__).replace("unittest.mock", "")  # just a trick to get path
    import os as _os
    _ws_root = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    if _ws_root not in sys.path:
        sys.path.insert(0, _ws_root)
    # Import real skills module so LoadedSkill/SkillMetadata are available
    skills_mod = ModuleType("skills")
    skills_mod.__path__ = [_os.path.join(_ws_root, "skills")]
    sys.modules["skills"] = skills_mod
    _spec = importlib.util.spec_from_file_location("skills.loader", _os.path.join(_ws_root, "skills", "loader.py"))
    _loader_mod = importlib.util.module_from_spec(_spec)
    sys.modules["skills.loader"] = _loader_mod
    _spec.loader.exec_module(_loader_mod)

if "coordinator" not in sys.modules:
    # Try importing real coordinator first
    try:
        import coordinator as _coord  # noqa: F401
    except ImportError:
        coordinator_mod = ModuleType("coordinator")
        coordinator_mod.get_children = MagicMock()
        coordinator_mod.get_parent_context = MagicMock()
        coordinator_mod.build_children_description = MagicMock()
        coordinator_mod.route_task_to_team = MagicMock()
        coordinator_mod.route_task_to_team.name = "route_task_to_team"
        sys.modules["coordinator"] = coordinator_mod

# Don't mock prompt or coordinator if they can be imported from the workspace-template dir
# test_prompt.py and test_coordinator.py need the real modules
