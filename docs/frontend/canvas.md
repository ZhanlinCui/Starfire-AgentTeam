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

Nodes are **selectable** — clicking a node highlights it with a blue border/ring and opens the [Side Panel](#side-panel). Clicking the canvas background (pane) deselects the current node.

Status colors include a **pulse animation** for the `provisioning` state, giving clear visual feedback that the workspace is starting up.

The node reflects `active_tasks` from the workspace heartbeat:

| `active_tasks` | Display |
|----------------|---------|
| 0 | Normal green node |
| 1-5 | Green node + small task count badge |
| > 5 | Amber node + count (getting busy) |

There are **no edges** between workspaces — parent/child relationships are rendered as [embedded sub-workspaces](#team-visualization-embedded-sub-workspaces) inside the parent node. Users nest workspaces by dragging one inside another.

### Nesting Mechanic

React Flow doesn't support native drag-into-group for setting parent/child — this is custom. The implementation uses React Flow's `getIntersectingNodes()` during drag to detect overlap with other nodes.

**How it works:**
1. `onNodeDrag` — checks which nodes the dragged node overlaps with, finds the first valid drop target (not self, not a descendant of dragged node)
2. Valid drop targets get a **green ring highlight** (`border-green-500 ring-2 scale-105`) via `dragOverNodeId` in the Zustand store
3. `onNodeDragStop` — if over a target, calls `nestNode(draggedId, targetId)` which does an optimistic edge update + `PATCH /workspaces/:id` with `parent_id`
4. If dropped on empty canvas background, un-nests the node (sets `parent_id` to null)

Circular hierarchy prevention: `isDescendant(ancestorId, nodeId)` walks the parent chain to ensure you can't drop a node onto its own descendant.

The Canvas component is wrapped in `ReactFlowProvider` to enable the `useReactFlow()` hook for `getIntersectingNodes()`.

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
| `TASK_UPDATED` | Node shows current task banner (amber pulsing dot) |
| `ACTIVITY_LOGGED` | No-op in store (ActivityTab polls for details) |

The flow: Platform broadcasts event via Redis pub/sub -> WebSocket handler pushes to connected clients -> Canvas updates Zustand state -> React Flow re-renders.

See [WebSocket Events](../api-protocol/websocket-events.md) for the full JSON payload format of each event.

## Side Panel

Clicking a workspace node opens a **480px-wide side panel** on the right edge of the screen (`canvas/src/components/SidePanel.tsx`). The panel header shows the workspace name, role, and a live status dot. When the agent has an active task (`current_task` from heartbeat), an amber pulsing banner appears below the tab bar showing what the agent is currently working on. The panel contains eleven tabs:

| Tab | Component | Description |
|-----|-----------|-------------|
| **Details** | `DetailsTab` | Inline editing of name/role/tier, editable Agent Card (JSON), Restart button for offline/failed, peer list, delete with confirmation |
| **Activity** | `ActivityTab` | Comprehensive activity log — A2A communications (with request/response bodies, duration), task updates, agent logs, errors. Type filters, auto-refresh (5s), expandable JSON details |
| **Chat** | `ChatTab` | Send A2A `message/send` via platform proxy, markdown rendering (react-markdown + remark-gfm), session persistence (localStorage), user-friendly error messages for 502/503/timeout |
| **Settings** | `SettingsTab` | Configure LLM provider + API keys per workspace via `/workspaces/:id/secrets`, quick-set rows for common keys |
| **Terminal** | `TerminalTab` | Shell access into workspace container via WebSocket (`WS /workspaces/:id/terminal`), xterm.js with dark theme |
| **Files** | `FilesTab` | VS Code-style file explorer with tree view, inline editor, create/delete files |
| **Config** | `ConfigTab` | JSON editor for workspace config, load via `GET /workspaces/:id/config`, save changes |
| **Memory** | `MemoryTab` | Browse key/value memory entries from `GET /workspaces/:id/memory`, add new entries with optional TTL |
| **Traces** | `TracesTab` | Langfuse LLM traces — name, latency, token usage, cost, expandable I/O |
| **Events** | `EventsTab` | Workspace-scoped structure event log from `GET /events/:workspaceId`, color-coded by event type |

Tab state is managed in the Zustand store via `panelTab` and `setPanelTab`. The panel closes when the user clicks the close button or clicks the canvas background.

The **DetailsTab** integrates directly with the store — edits update the node via `updateNodeData()`, delete removes it via `removeNode()`, Restart triggers `POST /workspaces/:id/restart`. Also includes Agent Management (assign/replace/remove model) and Replace Agent Folder (upload folder to swap agent files with confirmation).

The **Settings tab** stores API keys in the `workspace_secrets` table — values are never exposed to the browser (only key names are returned by `GET /workspaces/:id/secrets`).

The **Terminal tab** uses xterm.js with a WebSocket connection to a Docker exec session inside the workspace container. Sessions have a 30-minute idle timeout.

The **Files tab** provides a VS Code-style file explorer:
- Tree view with collapsible directories and file icons by extension
- Inline editor with monospace font, Ctrl/Cmd+S to save, Tab inserts spaces
- Create new files with path input, delete files with confirmation
- File operations via `GET/PUT/DELETE /workspaces/:id/files/*path`

## Canvas Chrome

### Toolbar

Fixed top-center bar showing the Starfire logo, live workspace status counts (online/offline/provisioning/failed), total workspace count, and a search button (`⌘K`).

### Search (⌘K)

Press `Cmd+K` or click the search button to open the search dialog. Fuzzy search across workspace name, role, and status. Click a result to select the node and open the Details panel. State managed in Zustand store (`searchOpen`/`setSearchOpen`).

### Empty State

When no workspaces exist, shows a visual getting-started guide with keyboard shortcut reference (template palette, ⌘K search, right-click, drag-to-nest).

### Toast Notifications

Global notification system (`showToast()` callable from any component). Context menu actions show success/error toasts. Auto-dismiss after 4 seconds, slide-up animation.

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `⌘K` | Open search dialog |
| `Escape` | Close context menu → close side panel (cascading) |
| `Ctrl/Cmd+S` | Save file (in Files tab editor) |
| `Right-click` | Open context menu on workspace node |

### Template Palette

Left sidebar toggled by the grid icon (top-left). Lists all available workspace templates from `GET /templates` with name, description, tier badge, and skill list. Click a template to deploy a new workspace. Includes "Import Agent Folder" button to upload any agent framework's folder (OpenClaw, Claude Code, Codex) as a new template.

### Right-Click Context Menu

Right-clicking a workspace node shows a context menu with:
- Details / Chat / Terminal — open side panel tabs
- Export Bundle — downloads `.bundle.json`
- Duplicate — exports then re-imports with new IDs
- Expand to Team / Collapse Team — team expansion via `POST /workspaces/:id/expand` or `/collapse`
- Extract from Team — for child nodes, un-nests from parent (sets `parent_id` to null)
- Restart — for offline/failed workspaces
- Delete — removes workspace

### Bundle Drop Zone

Drag a `.bundle.json` file onto the canvas to import a workspace tree via `POST /bundles/import`. Shows blue overlay during drag, import progress spinner, and success/error toast.

## Creating Workspaces

### Quick Create Dialog

A floating "**+ New Workspace**" button appears in the bottom-right corner when no node is selected (`canvas/src/components/CreateWorkspaceDialog.tsx`). Clicking it opens a modal dialog with fields for:

- **Name** (required)
- **Role** (optional)
- **Tier** (1–4 dropdown)
- **Parent Workspace ID** (optional — leave empty for root-level)

On submit, the dialog sends `POST /workspaces` with the form data and a random canvas position. The workspace node appears on the canvas once the platform broadcasts the creation event via WebSocket.

### Template Palette (planned)

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

## Team Visualization (Embedded Sub-Workspaces)

When a workspace is expanded into a team, children render **inside** the parent node as recursive mini-cards:

- Parent node dynamically sizes based on nesting depth:
  - No children: 210-280px
  - With children: 320-450px
  - With grandchildren: 400-560px
- Children appear as clickable `TeamMemberChip` components in a "Team Members" single-column layout
- Each child chip mirrors the parent card layout: status dot + gradient bar, name, tier badge, skills pills, status label, active tasks, descendant count badge
- **Recursive rendering**: sub-cards can contain their own "Team" section with further nested sub-cards, up to `MAX_NESTING_DEPTH = 3` levels
- `countDescendants()` helper (memoized, with cycle-protection via `visited` Set) counts all descendants recursively; badge shows total, not just direct children
- Click a child chip to select it and open its side panel
- **Eject/Extract**: each child chip shows a sky-blue eject button (arrow-up-right icon) on hover to extract it from the team (sets `parent_id` to null, unhides node)
- No separate canvas nodes or edges for parent→child relationships
- Children are hidden from React Flow (`hidden: true`) but exist in the store; `nestNode` sets `hidden: !!targetId` so nodes hide when nested and reappear when un-nested
- Double-click a team node to zoom/fit to the parent area
- Parent shows a descendant count badge in the header
- Callbacks (`onSelect`, `onExtract`) passed as props to avoid N+1 Zustand subscriptions per chip
- `useHierarchyInfo` consolidated hook: single stable selector returns children, `hasGrandchildren`, and `descendantCount` — avoids double `s.nodes` subscription
- `EmbeddedTeam` wrapper component isolates the `allNodes` subscription so it only mounts when children exist

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
    // Don't set React Flow parentId — children render embedded inside WorkspaceNode
    hidden: !!ws.parent_id, // Hide child nodes from canvas
    data: {
      name: ws.name,
      status: ws.status,
      tier: ws.tier,
      agentCard: ws.agent_card,
      activeTasks: ws.active_tasks,
      collapsed: ws.collapsed,
      url: ws.url,
      parentId: ws.parent_id,
      currentTask: ws.current_task || "",
    }
  }))
  setNodes(nodes)
}
```

### Zustand Store Shape

The canvas store (`canvas/src/store/canvas.ts`) manages both React Flow state and UI selection state:

```typescript
interface CanvasState {
  // React Flow state
  nodes: Node<WorkspaceNodeData>[];
  edges: Edge[];

  // Selection / panel state
  selectedNodeId: string | null;
  panelTab: PanelTab; // "details" | "activity" | "chat" | "settings" | "terminal" | "files" | "config" | "memory" | "traces" | "events"

  // Actions
  hydrate(workspaces): void;
  applyEvent(msg): void;
  onNodesChange(changes): void;
  savePosition(nodeId, x, y): void;
  selectNode(id: string | null): void;
  setPanelTab(tab: PanelTab): void;
  getSelectedNode(): Node | null;
  updateNodeData(id, data): void;  // patch node data in-place
  removeNode(id): void;            // remove node + edges + clear selection
}
```

`removeNode` cleans up edges connected to the removed node, properly re-parents children (using `n.data.parentId`, not React Flow's layout `parentId`), sets `hidden` correctly on re-parented children, and clears selection if the removed node was selected. The `WORKSPACE_REMOVED` event handler mirrors this logic — re-parenting children and clearing stale selection.

Edges array is empty — parent/child relationships are rendered as embedded sub-workspaces inside the parent node, not as React Flow edges.

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
