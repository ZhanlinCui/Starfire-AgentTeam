# Canvas UI (Next.js Frontend)

The canvas is the visual interface where users build and manage their AI org chart.

## Technology

- **Next.js 15** with App Router
- **React Flow** (xyflow) for the node-based canvas
- **Zustand** for state management
- **WebSocket** for real-time updates from the platform

## React Flow Canvas

Each workspace is a `WorkspaceNode` rendered from its Agent Card. The node displays:

- Workspace name
- Tier badge
- Online/offline status (with busy indicator from `active_tasks`)
- Skill list

The node reflects `active_tasks` from the workspace heartbeat:

| `active_tasks` | Display |
|----------------|---------|
| 0 | Normal green node |
| 1-5 | Green node + small task count badge |
| > 5 | Amber node + count (getting busy) |

Edges between workspaces are rendered **automatically from the hierarchy** (parent/child relationships). There is no manual edge drawing — users nest workspaces by dragging one inside another.

### Nesting Mechanic

React Flow doesn't support native drag-into-group for setting parent/child — this is custom. Each workspace node acts as a drop zone. When dragging a node, valid parent workspaces highlight as drop targets. On drop, immediate `PATCH /workspaces/:id` with `parent_id` — no confirmation dialog. Nesting should feel like dragging files into folders.

```typescript
// canvas/src/store/canvas.ts

const onNodeDrop = async (draggedId: string, targetId: string) => {
  // prevent dropping onto itself or own descendant
  if (draggedId === targetId) return
  if (isDescendant(draggedId, targetId)) return

  await api.patch(`/workspaces/${draggedId}`, { parent_id: targetId })
  // platform broadcasts WORKSPACE_MOVED → canvas updates via WebSocket
}

const onNodeDropOnCanvas = async (draggedId: string) => {
  await api.patch(`/workspaces/${draggedId}`, { parent_id: null })
}
```

The platform validates the move — rejects circular hierarchies or invalid targets with 400. Canvas shows a toast and snaps the node back on rejection.

## Live Updates via WebSocket

The canvas maintains a persistent WebSocket connection to the Go platform at `/ws`. When the platform broadcasts a structure event, the canvas updates automatically:

| Event | Canvas Effect |
|-------|--------------|
| `WORKSPACE_PROVISIONING` | Node appears with spinner |
| `WORKSPACE_ONLINE` | Node turns green |
| `WORKSPACE_OFFLINE` | Node turns gray |
| `WORKSPACE_PROVISION_FAILED` | Node turns red with retry button |
| `WORKSPACE_DEGRADED` | Node shows warning indicator |
| `WORKSPACE_REMOVED` | Node removed |
| `WORKSPACE_EXPANDED` | Node gains team badge, zoom-in available |
| `WORKSPACE_COLLAPSED` | Team collapsed back to single node |
| `WORKSPACE_MOVED` | Edges re-rendered for new parent position |
| `AGENT_ASSIGNED` | Node updates with agent/model info |
| `AGENT_REMOVED` | Node shows unassigned state |
| `AGENT_REPLACED` | Node updates model info |
| `AGENT_MOVED` | Source node clears agent, target node gains agent |
| `AGENT_CARD_UPDATED` | Node updates skill badges |

The flow: Platform broadcasts event via Redis pub/sub -> WebSocket handler pushes to connected clients -> Canvas updates Zustand state -> React Flow re-renders.

See [WebSocket Events](../api-protocol/websocket-events.md) for the full JSON payload format of each event.

## Creating Workspaces

There are no blank workspaces. Every workspace starts from a template, a bundle, or a duplication. Three ways to add a workspace to the canvas:

### 1. Template Palette

A sidebar panel listing available workspace templates. Templates come from `workspace-configs-templates/` — each folder is a template. The platform serves them via `GET /templates`.

**Flow:**
1. User opens the template palette (sidebar button or keyboard shortcut)
2. Palette shows available templates with name, description, and tier
3. User clicks a template
4. A quick config modal appears (pre-filled from template defaults):
   - Workspace name
   - Model selection (dropdown)
   - Parent workspace (dropdown — defaults to root level)
5. User confirms
6. Canvas sends `POST /workspaces` with template ref + overrides:
   ```json
   {
     "template": "seo-agent",
     "name": "Reno Stars SEO Agent",
     "model": "anthropic:claude-sonnet-4-6",
     "tier": 1,
     "parent_id": null,
     "canvas": { "x": 240, "y": 180 }
   }
   ```
7. Platform reads full config from `workspace-configs-templates/seo-agent/config.yaml`, applies overrides, provisions
8. New node appears on canvas with spinner → green when online

Template-based creation (`POST /workspaces`) and bundle-based creation (`POST /bundles/import`) are separate endpoints — different shape, different logic.

### 2. Drop Bundle

Drag a `.bundle.json` file onto the canvas. See [Bundle Interactions](#bundle-interactions) below.

### 3. Duplicate Node

Right-click an existing node → "Duplicate". This exports the workspace as a bundle and re-imports it with a new ID. The duplicate is independent — changes to one do not affect the other.

## Bundle Interactions

- **Export:** Right-click node -> "Export as bundle" -> downloads `.bundle.json`
- **Import:** Drag `.bundle.json` onto canvas -> `POST /bundles/import` -> platform provisions workspace tree -> new nodes appear
- **Duplicate:** Right-click node -> "Duplicate" -> export + re-import with new IDs

## Team Zoom-In

When a workspace is expanded into a team:
- The node shows a badge indicating it contains sub-workspaces
- Clicking/zooming into the node reveals the sub-workspace nodes inside
- From the top-level view, the team appears as a single node
- Sub-workspace nodes are only visible when zoomed into the parent

See [Team Expansion](../agent-runtime/team-expansion.md) for the full mechanics.

## Initial Hydration

On first load, the canvas hydrates from a single HTTP call, then switches to WebSocket for real-time deltas:

```typescript
async function hydrate() {
  // open socket FIRST to avoid missing events
  // that fire between HTTP response and socket connect
  socket.connect()

  // single call — returns workspaces with layout positions inline
  const workspaces = await api.get("/workspaces")

  // build initial React Flow nodes + edges from parent_id hierarchy
  canvasStore.hydrate(workspaces)
}
```

Only one HTTP call is needed — `GET /workspaces` JOINs `canvas_layouts` and returns positions inline. No separate layout fetch:

```go
// platform/internal/handlers/workspace.go

SELECT w.*, COALESCE(cl.x, 0) AS x, COALESCE(cl.y, 0) AS y,
       COALESCE(cl.collapsed, false) AS collapsed
FROM workspaces w
LEFT JOIN canvas_layouts cl ON cl.workspace_id = w.id
WHERE w.status != 'removed'
```

`LEFT JOIN` so new workspaces without a saved position default to x=0, y=0 — React Flow auto-places them, then saves position on first drag.

The canvas builds React Flow nodes directly from this response:

```typescript
function hydrate(workspaces: WorkspaceRow[]) {
  const nodes = workspaces.map(ws => ({
    id: ws.id,
    type: "workspaceNode",
    position: { x: ws.x, y: ws.y },
    parentId: ws.parent_id ?? undefined,
    data: {
      name: ws.name,
      status: ws.status,
      tier: ws.tier,
      agentCard: ws.agent_card,
      activeTasks: ws.active_tasks,
      collapsed: ws.collapsed,
    }
  }))
  setNodes(nodes)
}
```

Edges are derived from the parent/child hierarchy — no separate topology endpoint needed.

Node positions are persisted in Postgres (`canvas_layouts` table), not browser localStorage. This ensures the layout survives browser clears and is consistent across machines.

Positions save on drag **end** only — React Flow's `onNodeDragStop` fires when the user releases the mouse, not `onNodeDrag` which fires every pixel. A single `PATCH /workspaces/:id` with the final position.

When a parent node is dragged, React Flow moves all children automatically — only the parent's new position gets saved to the DB. Children retain their relative positions unchanged. A child's DB position only updates when the user explicitly drags that child node within its parent.

**Why connect WebSocket before the HTTP call returns:** If you connect after hydration, there's a race window where a workspace goes online between your HTTP response and socket connect — you'd miss the event and show stale state. Connecting first means events that arrive before hydration completes queue up and get applied on top.

WebSocket events are **idempotent** — applying `WORKSPACE_ONLINE` on a node that's already online is a no-op.

## WebSocket Reconnection

When the WebSocket connection drops (network hiccup, platform restart), the canvas reconnects with exponential backoff and re-hydrates from HTTP:

```typescript
// canvas/src/store/socket.ts

class ReconnectingSocket {
  private attempt = 0

  connect() {
    this.ws = new WebSocket(WS_URL)

    this.ws.onclose = () => {
      const delay = Math.min(1000 * 2 ** this.attempt, 30000)
      this.attempt++
      setTimeout(() => this.connect(), delay)
    }

    this.ws.onopen = () => {
      this.attempt = 0
      // re-hydrate to catch missed events during disconnect
      this.rehydrate()
    }
  }

  async rehydrate() {
    const workspaces = await api.get("/workspaces")
    canvasStore.hydrate(workspaces)
  }
}
```

Re-hydrate on every reconnect — don't try to replay missed events, just fetch current state. Any events that fired during the disconnect are already reflected in the HTTP response.

Workspace agents use the same pattern (exponential backoff reconnect) but don't re-hydrate — missed peer events just mean the system prompt might be slightly stale until the next relevant event fires on the 30s heartbeat cycle.

## Environment Variables

```
NEXT_PUBLIC_PLATFORM_URL=http://localhost:8080
NEXT_PUBLIC_WS_URL=ws://localhost:8080/ws
```

## Related Docs

- [Agent Card](../agent-runtime/agent-card.md) — Drives node rendering
- [Bundle System](../agent-runtime/bundle-system.md) — Import/export on canvas
- [Platform API](../api-protocol/platform-api.md) — Backend the canvas talks to
- [Communication Rules](../api-protocol/communication-rules.md) — How hierarchy drives edges
- [Registry & Heartbeat](../api-protocol/registry-and-heartbeat.md) — Events that drive live updates
- [WebSocket Events](../api-protocol/websocket-events.md) — Full event payload reference
- [Team Expansion](../agent-runtime/team-expansion.md) — How team zoom-in works
