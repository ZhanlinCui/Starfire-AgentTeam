"""Delegation tool for sending tasks to peer workspaces via A2A.

RBAC enforcement
----------------
The calling workspace must hold a role that grants the ``"delegate"`` action
(see ``tools/audit.ROLE_PERMISSIONS``).  The roles are read from
``config.yaml`` under ``rbac.roles`` at first call and cached for the life of
the process.  If the config cannot be loaded, the workspace defaults to the
``"operator"`` role (full access) so that agents remain functional in
lightweight / test environments.

Audit trail
-----------
Every delegation attempt — including RBAC denials, discovery failures, and
A2A-level errors — is appended as a JSON Lines record to the audit log
(default: ``/var/log/starfire/audit.jsonl``, overridden by ``AUDIT_LOG_PATH``).
The ``trace_id`` field (a UUID v4) is shared across all events that belong to
the same delegation attempt, enabling end-to-end trace reconstruction.

OpenTelemetry
-------------
A ``task_delegate`` span is created for every delegation.  W3C TraceContext
headers (``traceparent`` / ``tracestate``) are injected into the outgoing HTTP
request so the receiving workspace can parent its ``task_receive`` span to the
same distributed trace.  The current traceparent is also written into the A2A
metadata payload as a fallback for receivers that cannot access HTTP headers.
"""

import asyncio
import os
import uuid

import httpx
from langchain_core.tools import tool

from tools.audit import check_permission, get_workspace_roles, log_event
from tools.telemetry import (
    A2A_SOURCE_WORKSPACE,
    A2A_TARGET_WORKSPACE,
    A2A_TASK_ID,
    WORKSPACE_ID_ATTR,
    get_current_traceparent,
    get_tracer,
    inject_trace_headers,
)

PLATFORM_URL = os.environ.get("PLATFORM_URL", "http://platform:8080")
WORKSPACE_ID = os.environ.get("WORKSPACE_ID", "")
DELEGATION_RETRY_ATTEMPTS = int(os.environ.get("DELEGATION_RETRY_ATTEMPTS", "3"))
DELEGATION_RETRY_DELAY = float(os.environ.get("DELEGATION_RETRY_DELAY", "5.0"))
DELEGATION_TIMEOUT = float(os.environ.get("DELEGATION_TIMEOUT", "120.0"))


@tool
async def delegate_to_workspace(
    workspace_id: str,
    task: str,
) -> dict:
    """Delegate a task to a peer workspace via A2A protocol.

    Args:
        workspace_id: The ID of the target workspace to delegate to.
        task: The task description to send to the peer.

    Returns:
        A dict with the result or error information.
    """
    # One trace_id links every audit event for this delegation attempt.
    task_id = str(uuid.uuid4())

    # --- RBAC check -----------------------------------------------------------
    roles, custom_perms = get_workspace_roles()
    if not check_permission("delegate", roles, custom_perms):
        log_event(
            event_type="rbac",
            action="rbac.deny",
            resource=workspace_id,
            outcome="denied",
            trace_id=task_id,
            attempted_action="delegate",
            roles=roles,
        )
        return {
            "success": False,
            "error": (
                "RBAC: this workspace does not have the 'delegate' permission. "
                f"Current roles: {roles}"
            ),
        }

    # Log that the action was allowed by RBAC before attempting it.
    log_event(
        event_type="delegation",
        action="delegate",
        resource=workspace_id,
        outcome="allowed",
        trace_id=task_id,
        target_workspace_id=workspace_id,
        task_preview=task[:200],
    )

    # ── OTEL: task_delegate span ─────────────────────────────────────────────
    # Started here (after RBAC) so that it spans discovery + A2A send.
    # The span is a child of the currently active llm_call/task_receive span,
    # forming a complete picture of the outbound delegation in the trace.
    tracer = get_tracer()

    with tracer.start_as_current_span("task_delegate") as delegate_span:
        delegate_span.set_attribute(WORKSPACE_ID_ATTR, WORKSPACE_ID)
        delegate_span.set_attribute(A2A_SOURCE_WORKSPACE, WORKSPACE_ID)
        delegate_span.set_attribute(A2A_TARGET_WORKSPACE, workspace_id)
        delegate_span.set_attribute(A2A_TASK_ID, task_id)
        delegate_span.set_attribute("a2a.task_preview", task[:256])

        async with httpx.AsyncClient(timeout=DELEGATION_TIMEOUT) as client:
            # --- Discover the target workspace URL ----------------------------
            try:
                discover_resp = await client.get(
                    f"{PLATFORM_URL}/registry/discover/{workspace_id}",
                    headers={"X-Workspace-ID": WORKSPACE_ID},
                )
                if discover_resp.status_code == 403:
                    log_event(
                        event_type="delegation",
                        action="delegate",
                        resource=workspace_id,
                        outcome="failure",
                        trace_id=task_id,
                        reason="platform_forbidden",
                        http_status=403,
                    )
                    return {
                        "success": False,
                        "error": f"Not authorized to communicate with {workspace_id}",
                    }
                if discover_resp.status_code == 404:
                    log_event(
                        event_type="delegation",
                        action="delegate",
                        resource=workspace_id,
                        outcome="failure",
                        trace_id=task_id,
                        reason="workspace_not_found",
                        http_status=404,
                    )
                    return {
                        "success": False,
                        "error": f"Workspace {workspace_id} not found",
                    }
                if discover_resp.status_code != 200:
                    log_event(
                        event_type="delegation",
                        action="delegate",
                        resource=workspace_id,
                        outcome="failure",
                        trace_id=task_id,
                        reason="discovery_error",
                        http_status=discover_resp.status_code,
                    )
                    return {
                        "success": False,
                        "error": f"Discovery failed with status {discover_resp.status_code}",
                    }

                target_url = discover_resp.json().get("url")
                if not target_url:
                    log_event(
                        event_type="delegation",
                        action="delegate",
                        resource=workspace_id,
                        outcome="failure",
                        trace_id=task_id,
                        reason="no_url_in_registry",
                    )
                    return {
                        "success": False,
                        "error": f"Workspace {workspace_id} has no URL",
                    }

                delegate_span.set_attribute("a2a.target_url", target_url)

            except Exception as e:
                log_event(
                    event_type="delegation",
                    action="delegate",
                    resource=workspace_id,
                    outcome="failure",
                    trace_id=task_id,
                    reason="discovery_exception",
                    error=str(e),
                )
                try:
                    delegate_span.record_exception(e)
                except Exception:
                    pass
                return {"success": False, "error": f"Discovery error: {e}"}

            # --- Send A2A message/send with retry -----------------------------
            # Inject W3C TraceContext headers so the receiving workspace can
            # attach its task_receive span to the current distributed trace.
            # We also embed traceparent in the A2A metadata as a fallback.
            outgoing_headers = inject_trace_headers(
                {
                    "Content-Type": "application/json",
                    "X-Workspace-ID": WORKSPACE_ID,
                }
            )
            traceparent = get_current_traceparent()

            last_error = None
            for attempt in range(DELEGATION_RETRY_ATTEMPTS):
                delegate_span.set_attribute("a2a.attempt", attempt + 1)
                try:
                    a2a_resp = await client.post(
                        target_url,
                        headers=outgoing_headers,
                        json={
                            "jsonrpc": "2.0",
                            "method": "message/send",
                            "id": f"delegation-{workspace_id}-{attempt}",
                            "params": {
                                "message": {
                                    "role": "user",
                                    "parts": [{"kind": "text", "text": task}],
                                    "messageId": f"msg-{workspace_id}-{attempt}",
                                },
                                "metadata": {
                                    "parent_task_id": task_id,
                                    "source_workspace_id": WORKSPACE_ID,
                                    # W3C traceparent for receivers that read
                                    # it from the JSON payload rather than headers
                                    "traceparent": traceparent,
                                },
                            },
                        },
                    )

                    if a2a_resp.status_code == 200:
                        result = a2a_resp.json()
                        if "result" in result:
                            task_result = result["result"]
                            # Extract text from artifacts
                            artifacts = task_result.get("artifacts", [])
                            texts = []
                            for artifact in artifacts:
                                for part in artifact.get("parts", []):
                                    if part.get("kind") == "text":
                                        texts.append(part["text"])
                            log_event(
                                event_type="delegation",
                                action="delegate",
                                resource=workspace_id,
                                outcome="success",
                                trace_id=task_id,
                                target_workspace_id=workspace_id,
                                attempt=attempt + 1,
                            )
                            delegate_span.set_attribute("a2a.success", True)
                            return {
                                "success": True,
                                "response": "\n".join(texts) if texts else str(task_result),
                                "workspace_id": workspace_id,
                            }
                        if "error" in result:
                            last_error = result["error"].get("message", str(result["error"]))
                            break  # Don't retry explicit RPC errors

                except (httpx.ConnectError, httpx.TimeoutException) as e:
                    last_error = str(e)
                    if attempt < DELEGATION_RETRY_ATTEMPTS - 1:
                        await asyncio.sleep(DELEGATION_RETRY_DELAY * (attempt + 1))
                    continue

        log_event(
            event_type="delegation",
            action="delegate",
            resource=workspace_id,
            outcome="failure",
            trace_id=task_id,
            target_workspace_id=workspace_id,
            attempts=DELEGATION_RETRY_ATTEMPTS,
            last_error=str(last_error),
        )
        delegate_span.set_attribute("a2a.success", False)
        delegate_span.set_attribute("a2a.last_error", str(last_error or ""))

        return {
            "success": False,
            "error": last_error,
            "workspace_id": workspace_id,
            "message": f"Delegation to {workspace_id} failed after {DELEGATION_RETRY_ATTEMPTS} attempts.",
        }
