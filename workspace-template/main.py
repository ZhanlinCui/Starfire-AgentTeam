"""Workspace runtime entry point.

Loads config -> loads skills -> creates agent -> wraps in A2A -> registers -> starts heartbeat.
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

from a2a_executor import LangGraphA2AExecutor
from agent import create_agent
from cli_executor import CLIAgentExecutor
from config import load_config
from coordinator import get_children, get_parent_context, build_children_description, route_task_to_team
from heartbeat import HeartbeatLoop
from plugins import load_plugins
from prompt import build_system_prompt, get_peer_capabilities
from skills.loader import load_skills
from tools.approval import request_approval
from tools.delegation import delegate_to_workspace
from tools.memory import commit_memory, search_memory
from tools.sandbox import run_code


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

    # 2. Load plugins (ECC, Superpowers, etc.)
    plugins = load_plugins()
    if plugins.plugin_names:
        print(f"Plugins: {', '.join(plugins.plugin_names)}")

    # 3. Load skills — workspace skills + plugin skills (deduplicated by ID)
    loaded_skills = load_skills(config_path, config.skills)
    seen_skill_ids = {s.metadata.id for s in loaded_skills}

    for plugin_skills_dir in plugins.skill_dirs:
        plugin_skill_names = [
            d for d in os.listdir(plugin_skills_dir)
            if os.path.isdir(os.path.join(plugin_skills_dir, d))
        ]
        for skill in load_skills(plugin_skills_dir, plugin_skill_names):
            if skill.metadata.id not in seen_skill_ids:
                loaded_skills.append(skill)
                seen_skill_ids.add(skill.metadata.id)

    print(f"Loaded {len(loaded_skills)} skills: {[s.metadata.id for s in loaded_skills]}")

    # 4. Gather tools from skills + built-in delegation tool
    all_tools = [delegate_to_workspace, request_approval, commit_memory, search_memory, run_code]
    for skill in loaded_skills:
        all_tools.extend(skill.tools)

    # 5. Check if this workspace is a team coordinator (has children)
    children = await get_children()
    is_coordinator = len(children) > 0
    if is_coordinator:
        print(f"Coordinator mode: {len(children)} children ({[c.get('name') for c in children]})")
        all_tools.append(route_task_to_team)

    # 6. Fetch parent's shared context (if this is a child workspace)
    parent_context = await get_parent_context()
    if parent_context:
        print(f"Inherited {len(parent_context)} context files from parent")

    # 7. Fetch peer capabilities and build system prompt
    peers = await get_peer_capabilities(platform_url, workspace_id)

    coordinator_prompt = build_children_description(children) if is_coordinator else ""
    extra_prompts = list(plugins.prompt_fragments)
    if coordinator_prompt:
        extra_prompts.append(coordinator_prompt)

    system_prompt = build_system_prompt(
        config_path, workspace_id, loaded_skills, peers,
        prompt_files=config.prompt_files,
        plugin_rules=plugins.rules,
        plugin_prompts=extra_prompts,
        parent_context=parent_context,
    )

    # 7. Create the agent (runtime-dependent)
    is_cli_runtime = config.runtime != "langgraph"

    if is_cli_runtime:
        print(f"Runtime: {config.runtime} (CLI-based)")
        executor = CLIAgentExecutor(
            runtime=config.runtime,
            runtime_config=config.runtime_config,
            system_prompt=system_prompt,
            config_path=config_path,
        )
        agent = None  # No LangGraph agent needed
    else:
        print("Runtime: langgraph")
        agent = create_agent(config.model, all_tools, system_prompt)
        executor = LangGraphA2AExecutor(agent)

    # 8. Build Agent Card
    machine_ip = os.environ.get("HOSTNAME", get_machine_ip())
    workspace_url = f"http://{machine_ip}:{port}"

    agent_card = AgentCard(
        name=config.name,
        description=config.description,
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

    # 9. Wrap in A2A
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
    heartbeat = HeartbeatLoop(platform_url, workspace_id)
    heartbeat.start()

    # 10. Run the A2A server
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
