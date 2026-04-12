"""Workspace runtime entry point.

Loads config -> discovers adapter -> setup -> create executor -> wrap in A2A -> register -> heartbeat.
"""

import asyncio
import json
import os
import socket

import httpx
import uvicorn
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCard, AgentCapabilities, AgentSkill

from adapters import get_adapter, AdapterConfig
from config import load_config
from heartbeat import HeartbeatLoop
from preflight import run_preflight, render_preflight_report
from builtin_tools.awareness_client import get_awareness_config
import uuid as _uuid

from builtin_tools.telemetry import setup_telemetry, make_trace_middleware
from policies.namespaces import resolve_awareness_namespace


def get_machine_ip() -> str:  # pragma: no cover
    """Get the machine's IP for A2A discovery."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


async def main():  # pragma: no cover
    workspace_id = os.environ.get("WORKSPACE_ID", "workspace-default")
    config_path = os.environ.get("WORKSPACE_CONFIG_PATH", "/configs")
    platform_url = os.environ.get("PLATFORM_URL", "http://platform:8080")
    awareness_config = get_awareness_config()

    # 0. Initialise OpenTelemetry (no-op if packages not installed)
    setup_telemetry(service_name=workspace_id)

    # 1. Load config
    config = load_config(config_path)
    port = config.a2a.port
    preflight = run_preflight(config, config_path)
    render_preflight_report(preflight)
    if not preflight.ok:
        raise SystemExit(1)
    if awareness_config:
        awareness_namespace = resolve_awareness_namespace(
            workspace_id,
            awareness_config.get("namespace", ""),
        )
        print(f"Awareness enabled for namespace: {awareness_namespace}")

    # 1.5  Initialise governance adapter (no-op if disabled or package absent)
    from builtin_tools.governance import initialize_governance
    if config.governance.enabled:
        await initialize_governance(config.governance)
        print(f"Governance: Microsoft Agent Governance Toolkit enabled (mode={config.governance.policy_mode})")
    else:
        print("Governance: disabled (set governance.enabled: true in config.yaml to activate)")

    # 2. Create heartbeat (passed to adapter for task tracking)
    heartbeat = HeartbeatLoop(platform_url, workspace_id)

    # 3. Get adapter for this runtime
    runtime = config.runtime or "langgraph"
    adapter_cls = get_adapter(runtime)  # Raises KeyError if unknown — no silent fallback

    adapter = adapter_cls()
    print(f"Runtime: {runtime} ({adapter.display_name()})")

    # 4. Build adapter config
    adapter_config = AdapterConfig(
        model=config.model,
        system_prompt=None,  # Adapter builds its own prompt
        tools=config.skills,  # Skill names from config.yaml
        runtime_config=vars(config.runtime_config) if config.runtime_config else {},
        config_path=config_path,
        workspace_id=workspace_id,
        prompt_files=config.prompt_files,
        a2a_port=port,
        heartbeat=heartbeat,
    )

    # 5. Setup adapter and create executor
    # If setup fails, ensure heartbeat is stopped to prevent resource leak
    try:
        await adapter.setup(adapter_config)
        executor = await adapter.create_executor(adapter_config)
    except Exception:
        # heartbeat hasn't started yet but may have async tasks pending
        if hasattr(heartbeat, "stop"):
            try:
                await heartbeat.stop()
            except Exception:
                pass
        raise

    # 5.5. Initialise Temporal durable execution wrapper (optional)
    # Connects to TEMPORAL_HOST (default: localhost:7233) and starts a
    # co-located Temporal worker as a background asyncio task.
    # No-op with a warning log if Temporal is unreachable or temporalio
    # is not installed — all tasks fall back to direct execution transparently.
    from builtin_tools.temporal_workflow import create_wrapper as _create_temporal_wrapper
    temporal_wrapper = _create_temporal_wrapper()
    await temporal_wrapper.start()

    # Get loaded skills for agent card (adapter may have populated them)
    loaded_skills = getattr(adapter, "loaded_skills", [])

    # 6. Build Agent Card
    machine_ip = os.environ.get("HOSTNAME", get_machine_ip())
    workspace_url = f"http://{machine_ip}:{port}"

    agent_card = AgentCard(
        name=config.name,
        description=config.description or config.name,
        version=config.version,
        url=workspace_url,
        capabilities=AgentCapabilities(
            streaming=config.a2a.streaming,
            pushNotifications=config.a2a.push_notifications,
        ),
        skills=[
            AgentSkill(
                id=skill.metadata.id,
                name=skill.metadata.name,
                description=skill.metadata.description,
                tags=skill.metadata.tags,
                examples=skill.metadata.examples,
            )
            for skill in loaded_skills
        ],
        defaultInputModes=["text/plain", "application/json"],
        defaultOutputModes=["text/plain", "application/json"],
    )

    # 7. Wrap in A2A
    handler = DefaultRequestHandler(
        agent_executor=executor,
        task_store=InMemoryTaskStore(),
    )

    app = A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=handler,
    )

    # 8. Register with platform
    agent_card_dict = {
        "name": config.name,
        "description": config.description,
        "version": config.version,
        "url": workspace_url,
        "skills": [
            {
                "id": s.metadata.id,
                "name": s.metadata.name,
                "description": s.metadata.description,
                "tags": s.metadata.tags,
            }
            for s in loaded_skills
        ],
        "capabilities": {
            "streaming": config.a2a.streaming,
            "pushNotifications": config.a2a.push_notifications,
        },
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(
                f"{platform_url}/registry/register",
                json={
                    "id": workspace_id,
                    "url": workspace_url,
                    "agent_card": agent_card_dict,
                },
            )
            print(f"Registered with platform: {resp.status_code}")
        except Exception as e:
            print(f"Warning: failed to register with platform: {e}")

    # 9. Start heartbeat
    heartbeat.start()

    # 9b. Start skills hot-reload watcher (background task)
    # When a skill file changes the watcher reloads the skill module and calls
    # back into the adapter so the next A2A request uses the updated tools.
    if config.skills:
        try:
            from skill_loader.watcher import SkillsWatcher

            def _on_skill_reload(updated_skill):
                """Rebuild the LangGraph agent when a skill changes in-place."""
                if not hasattr(adapter, "loaded_skills"):
                    return
                # Replace the matching skill in the adapter's skill list
                adapter.loaded_skills = [
                    updated_skill if s.metadata.id == updated_skill.metadata.id else s
                    for s in adapter.loaded_skills
                ]
                # Rebuild the agent's tool list from updated skills
                if hasattr(adapter, "all_tools") and hasattr(adapter, "system_prompt"):
                    from builtin_tools.approval import request_approval
                    from builtin_tools.delegation import delegate_to_workspace
                    from builtin_tools.memory import commit_memory, search_memory
                    from builtin_tools.sandbox import run_code
                    base_tools = [delegate_to_workspace, request_approval,
                                  commit_memory, search_memory, run_code]
                    skill_tools = []
                    for sk in adapter.loaded_skills:
                        skill_tools.extend(sk.tools)
                    adapter.all_tools = base_tools + skill_tools
                    # Rebuild compiled agent so next ainvoke picks up new tools
                    try:
                        from agent import create_agent
                        new_agent = create_agent(
                            config.model, adapter.all_tools, adapter.system_prompt
                        )
                        executor.agent = new_agent
                        print(f"Skills hot-reload: '{updated_skill.metadata.id}' reloaded — "
                              f"{len(updated_skill.tools)} tool(s)")
                    except Exception as rebuild_err:
                        print(f"Skills hot-reload: agent rebuild failed: {rebuild_err}")

            skills_watcher = SkillsWatcher(
                config_path=config_path,
                skill_names=config.skills,
                on_reload=_on_skill_reload,
            )
            asyncio.create_task(skills_watcher.start())
            print(f"Skills hot-reload enabled for: {config.skills}")
        except Exception as e:
            print(f"Warning: skills watcher could not start: {e}")

    # 10. Run A2A server
    print(f"Workspace {workspace_id} starting on port {port}")
    # Wrap the ASGI app with W3C TraceContext extraction middleware so incoming
    # A2A HTTP requests propagate their trace context into _incoming_trace_context.
    built_app = make_trace_middleware(app.build())

    server_config = uvicorn.Config(
        built_app,
        host="0.0.0.0",
        port=port,
        log_level="info",
    )
    server = uvicorn.Server(server_config)

    # 10b. Schedule initial_prompt self-message after server is ready.
    # Only runs on first boot — creates a marker file to prevent re-execution on restart.
    initial_prompt_task = None
    # Marker file to prevent re-execution on restart. Try /configs first (persists),
    # fall back to /workspace (also persists as a Docker volume).
    initial_prompt_marker = os.path.join(config_path, ".initial_prompt_done")
    if not os.access(config_path, os.W_OK):
        initial_prompt_marker = "/workspace/.initial_prompt_done"
    if config.initial_prompt and not os.path.exists(initial_prompt_marker):
        async def _send_initial_prompt():
            """Wait for server to be ready, then send initial_prompt as self-message."""
            # Wait for the A2A server to accept connections
            ready = False
            for attempt in range(30):
                await asyncio.sleep(1)
                try:
                    async with httpx.AsyncClient(timeout=5.0) as client:
                        resp = await client.get(f"http://127.0.0.1:{port}/.well-known/agent.json")
                        if resp.status_code == 200:
                            ready = True
                            break
                except Exception:
                    continue

            if not ready:
                print("Initial prompt: server not ready after 30s, skipping", flush=True)
                return

            # Send initial prompt through the platform A2A proxy (not directly to self).
            # The proxy logs an a2a_receive with source_id=NULL (canvas-style),
            # broadcasts A2A_RESPONSE via WebSocket so the chat shows both the
            # prompt (as user message) and the response (as agent message).
            # Uses urllib in a thread to avoid asyncio/httpx streaming hangs.
            import json as _json
            import urllib.request

            def _do_send_sync():
                try:
                    payload = _json.dumps({
                        "method": "message/send",
                        "params": {
                            "message": {
                                "role": "user",
                                "messageId": f"initial-{_uuid.uuid4().hex[:8]}",
                                "parts": [{"kind": "text", "text": config.initial_prompt}],
                            },
                        },
                    }).encode()

                    req = urllib.request.Request(
                        f"{platform_url}/workspaces/{workspace_id}/a2a",
                        data=payload,
                        headers={"Content-Type": "application/json"},
                    )
                    with urllib.request.urlopen(req, timeout=600) as resp:
                        resp.read()  # consume body
                    print(f"Initial prompt: completed (status={resp.status})", flush=True)

                except Exception as e:
                    print(f"Initial prompt: failed — {e}", flush=True)
                    return

                # Write marker
                try:
                    with open(initial_prompt_marker, "w") as f:
                        f.write("done")
                except OSError:
                    pass

            print("Initial prompt: sending via platform proxy...", flush=True)
            loop = asyncio.get_event_loop()
            loop.run_in_executor(None, _do_send_sync)

        initial_prompt_task = asyncio.create_task(_send_initial_prompt())

    try:
        await server.serve()
    finally:
        # Cancel initial prompt if still running
        if initial_prompt_task and not initial_prompt_task.done():
            initial_prompt_task.cancel()
        # Gracefully stop the Temporal worker background task on shutdown
        await temporal_wrapper.stop()


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(main())
