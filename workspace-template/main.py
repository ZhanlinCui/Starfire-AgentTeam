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


def get_machine_ip() -> str:
    """Get the machine's IP for A2A discovery."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


async def main():
    workspace_id = os.environ.get("WORKSPACE_ID", "workspace-default")
    config_path = os.environ.get("WORKSPACE_CONFIG_PATH", "/configs")
    platform_url = os.environ.get("PLATFORM_URL", "http://platform:8080")

    # 1. Load config
    config = load_config(config_path)
    port = config.a2a.port

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
    await adapter.setup(adapter_config)
    executor = await adapter.create_executor(adapter_config)

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

    # 10. Run A2A server
    print(f"Workspace {workspace_id} starting on port {port}")
    server_config = uvicorn.Config(
        app.build(),
        host="0.0.0.0",
        port=port,
        log_level="info",
    )
    server = uvicorn.Server(server_config)
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
