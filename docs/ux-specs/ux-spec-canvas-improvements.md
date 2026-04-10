# Canvas UI/UX Spec: Three Priority Areas
**Author:** UI/UX Designer Agent  
**Date:** 2026-04-09  
**Status:** Draft v1.0  
**Audience:** Frontend Engineering  

---

## Table of Contents

1. [Settings Panel — Global Secrets CRUD](#1-settings-panel--global-secrets-crud)
2. [Onboarding / Deploy Interception Flow](#2-onboarding--deploy-interception-flow)
3. [Everything on UI — API-Only Feature Audit](#3-everything-on-ui--api-only-feature-audit)

---

---

# 1. Settings Panel — Global Secrets CRUD

## 1.1 Access Point: Gear Icon Placement

### Top Bar Anatomy (left → right)
```
[ Logo / Wordmark ]  [ Workspace breadcrumb ]         [ Search ]  [ Notifications 🔔 ]  [ Settings ⚙ ]  [ Avatar / Org ]
```

**Gear icon placement:** Far-right cluster, immediately left of the user avatar/org switcher. This mirrors conventions from Vercel, Linear, and GitHub — settings are always "behind" identity, never in the primary action zone.

- **Icon:** Standard gear/cog (24×24px, 2px stroke)
- **Tooltip:** "Settings" (appears on hover, 300ms delay)
- **Keyboard shortcut:** `G S` (press G then S — mnemonic: **G**o to **S**ettings). Display shortcut in tooltip: "Settings  G S"
- **Active state:** Icon fills with primary brand color, drawer opens
- **Badge indicator:** If any secrets are invalid/expired, show a red dot badge (8px) on the gear icon. This is a passive ambient indicator — does not pulse or animate.

---

## 1.2 Panel Layout: Slide-Out Drawer

**Decision: Right-side slide-out drawer (not modal, not dedicated page)**

**Rationale:**
- Settings are a secondary concern, not a primary task — a dedicated page route breaks flow
- Modals imply blocking; settings are non-blocking reference
- Right drawer is the established pattern for contextual panels (same as VS Code, Figma, Linear)
- Users need to see the canvas while checking which secrets are configured (e.g., "which agent is this key for?")

### Drawer Specifications

| Property | Value |
|---|---|
| Width | 480px (desktop), full-width (mobile <768px) |
| Height | 100vh, fixed |
| Position | Fixed right edge, overlays canvas with scrim |
| Scrim | rgba(0,0,0,0.3), click-outside closes drawer |
| Animation | Slide in from right: 220ms ease-out |
| Animation out | Slide out to right: 180ms ease-in |
| Z-index | 200 (above canvas, below toast notifications) |
| Focus trap | Yes — Tab cycles within drawer; Escape closes |

### Drawer Internal Layout

```
┌─────────────────────────────────────────┐
│ Settings                           [✕]  │  ← Header (56px, sticky)
│─────────────────────────────────────────│
│ [🔍 Search secrets...         ]         │  ← Search bar (48px, sticky below header)
│─────────────────────────────────────────│
│  NAVIGATION (left rail, 160px)          │  ← Vertical tab list
│  ● Secrets          │ [Secrets panel]   │
│    API Keys         │                   │
│  ○ Integrations     │                   │
│  ○ Organization     │                   │
│  ○ Appearance       │                   │
│  ○ Danger Zone      │                   │
│─────────────────────────────────────────│
│                                [footer] │  ← 56px sticky footer with Save / Cancel
└─────────────────────────────────────────┘
```

**Note:** For v1, only "Secrets / API Keys" section is in scope. Other nav items can be stubbed as "Coming soon" greyed entries to establish information architecture without blocking ship.

---

## 1.3 Secrets Panel Layout

### Wireframe: Secrets List View (READ)

```
┌─────────────────────────────────────────────────────────────┐
│ Secrets & API Keys                    [+ Add Secret]        │
│─────────────────────────────────────────────────────────────│
│ [🔍 Filter secrets...     ]  [All services ▾]  [Status ▾]  │
│─────────────────────────────────────────────────────────────│
│                                                             │
│ ▾ ANTHROPIC                                         [+ Add] │
│ ┌───────────────────────────────────────────────────────┐   │
│ │ 🟢  ANTHROPIC_API_KEY          ••••••••••••3f2a  [✎][🗑]│  │
│ │     Last validated: 2 hours ago                       │   │
│ └───────────────────────────────────────────────────────┘   │
│                                                             │
│ ▾ OPENROUTER                                        [+ Add] │
│ ┌───────────────────────────────────────────────────────┐   │
│ │ 🟡  OPENROUTER_API_KEY         ••••••••••••9c1e  [✎][🗑]│  │
│ │     Last validated: 3 days ago · Needs re-validation  │   │
│ └───────────────────────────────────────────────────────┘   │
│                                                             │
│ ▾ GITHUB                                            [+ Add] │
│ ┌───────────────────────────────────────────────────────┐   │
│ │ 🔴  GITHUB_TOKEN               ••••••••••••0000  [✎][🗑]│  │
│ │     Validation failed · Token may be expired          │   │
│ └───────────────────────────────────────────────────────┘   │
│                                                             │
│ ▾ LANGFUSE                                          [+ Add] │
│ ┌───────────────────────────────────────────────────────┐   │
│ │ ⚪  LANGFUSE_PUBLIC_KEY         Not configured        [✎] │  │
│ │     LANGFUSE_SECRET_KEY         Not configured        [✎] │  │
│ │     LANGFUSE_HOST               Not configured        [✎] │  │
│ └───────────────────────────────────────────────────────┘   │
│                                                             │
│ ▸ OPENAI  (collapsed)                               [+ Add] │
│ ▸ GROQ    (collapsed)                               [+ Add] │
└─────────────────────────────────────────────────────────────┘
```

### Status Indicator States

| Indicator | Color | Meaning | Trigger |
|---|---|---|---|
| 🟢 Valid | Green (#22c55e) | Key passed validation | Backend `/validate` returned 200 within last 24h |
| 🟡 Stale | Amber (#f59e0b) | Not validated recently | Last validated >24h ago |
| 🔴 Invalid | Red (#ef4444) | Validation failed | Backend returned 401/403 or connection refused |
| ⚪ Missing | Grey (#9ca3af) | Not yet configured | Key not in env/store |

**Validation is non-blocking:** Status indicators update asynchronously. On drawer open, the UI optimistically shows cached status, then fires a background re-validation call. If stale, spinner overlays the dot for up to 5s.

### Secret Row: Expanded State
```
┌───────────────────────────────────────────────────────────┐
│ 🟢  ANTHROPIC_API_KEY                             [✎] [🗑] │
│     sk-ant-••••••••••••••••••••••••••••••••••3f2a         │
│     Last validated: 2 hours ago · Used by 3 agents        │
└───────────────────────────────────────────────────────────┘
```
- Click secret row to expand → shows masked value + usage metadata
- "Used by N agents" is a link → clicking opens a popover listing agent names
- Masked format: show prefix (first 4 chars of key scheme, e.g. `sk-ant-`) + dots + last 4 chars

---

## 1.4 CREATE: Add New Secret

### Trigger Points
- "[+ Add Secret]" button in drawer header
- "[+ Add]" per service group header
- Inline "[✎]" on a "Not configured" row

### CREATE Wireframe: Inline Expand (not modal)

When triggered, the relevant service group expands an inline form **below** the group header:

```
▾ ANTHROPIC                                          [+ Add]
┌───────────────────────────────────────────────────────┐
│  ANTHROPIC_API_KEY                                    │
│  ┌─────────────────────────────────────────────────┐  │
│  │ sk-ant-api03-••••••••••••••••••••••••••••••••   │  │  ← Password input
│  └─────────────────────────────────────────────────┘  │
│  [👁 Show]                                            │
│                                                       │
│  ☑ Test connection before saving                      │
│                                                       │
│  [Cancel]                          [Test & Save →]    │
└───────────────────────────────────────────────────────┘
```

**For "+ Add Secret" (no group pre-selected):**

```
┌── Add New Secret ──────────────────────────────────────┐
│                                                        │
│  Service                                               │
│  ┌──────────────────────────────────────────────────┐  │
│  │ Select service...                              ▾ │  │
│  └──────────────────────────────────────────────────┘  │
│  Options: Anthropic, OpenRouter, GitHub, OpenAI,       │
│           Groq, Langfuse (Public Key), Langfuse        │
│           (Secret Key), Langfuse (Host), Other…        │
│                                                        │
│  Secret Name  (auto-filled on service select)          │
│  ┌──────────────────────────────────────────────────┐  │
│  │ ANTHROPIC_API_KEY                                │  │
│  └──────────────────────────────────────────────────┘  │
│  ⓘ This is the environment variable name used by       │
│    deployed agents. Use the suggested name unless      │
│    you have a specific reason to change it.            │
│                                                        │
│  Value                                                 │
│  ┌──────────────────────────────────────────────────┐  │
│  │ ••••••••••••••••••••••••••••••                   │  │
│  └──────────────────────────────────────────────────┘  │
│  [👁 Show]                                             │
│                                                        │
│  ☑ Test connection before saving                       │
│                                                        │
│  [Cancel]                           [Test & Save →]    │
└────────────────────────────────────────────────────────┘
```

### CREATE: Validation Rules

| Field | Rule | Error Message |
|---|---|---|
| Service | Required | "Select a service to continue" |
| Secret Name | Required, env var format `[A-Z_]+` | "Name must be uppercase letters and underscores only" |
| Secret Name | No duplicates within org | "A secret with this name already exists. Edit the existing one instead." |
| Value | Required, non-empty | "Enter the secret value" |
| Value | Min length per service (e.g. Anthropic keys are 93+ chars) | "This doesn't look like a valid Anthropic API key. Double-check and try again." |

### CREATE: "Test & Save" Flow

```
User clicks [Test & Save]
     │
     ▼
Button enters loading state: [Testing connection…  ◌]
     │
     ├── SUCCESS (200 from backend validation)
     │        │
     │        ▼
     │   Button briefly shows [✓ Connected!] (green, 1.5s)
     │   Form collapses, new secret appears in list with 🟢 badge
     │   Toast: "ANTHROPIC_API_KEY saved successfully"
     │
     └── FAILURE (401/403/timeout)
              │
              ▼
         Inline error appears below value field:
         ┌─────────────────────────────────────────────┐
         │ 🔴 Connection failed: API key was rejected  │
         │    Double-check the key and try again.      │
         │    [Save anyway]    [Try again]             │
         └─────────────────────────────────────────────┘
         Button returns to [Test & Save →]
```

**"Save anyway" option:** Saves the secret with 🔴 invalid status. This is intentional — users may be setting up keys before they're active (e.g., provisioning Anthropic access). Never block save.

---

## 1.5 UPDATE: Edit Existing Secret

### Trigger: Click [✎] on any secret row

The row expands inline to edit mode (same form as CREATE, but pre-populated):

```
┌───────────────────────────────────────────────────────┐
│ 🟢  ANTHROPIC_API_KEY                       [✎ active]│
│                                                       │
│  Value                                                │
│  ┌─────────────────────────────────────────────────┐  │
│  │ ••••••••••••••••••••••••••••••••••••••••••••••  │  │  ← Shows full masked value
│  └─────────────────────────────────────────────────┘  │
│  [👁 Show]  [Clear to retype]                         │
│                                                       │
│  ⚠ Changing this key will affect 3 agents that use it │
│                                                       │
│  [Cancel]                          [Test & Save →]    │
└───────────────────────────────────────────────────────┘
```

**Key behaviors:**
- The existing value is shown fully masked (all dots). User must click "Clear to retype" to enter a new value — this prevents accidental overwrites by pressing a key.
- After "Clear to retype" is clicked, input becomes a blank password field.
- "Used by N agents" warning appears if `n > 0`.
- "Test & Save" reruns validation. If user clears and saves empty value → treated as DELETE (prompt: "Are you sure you want to remove this secret?").

---

## 1.6 DELETE: Remove Secret

### Trigger: Click [🗑] on any secret row

**Inline confirmation (not a full modal — proportional response):**

```
┌───────────────────────────────────────────────────────┐
│ 🔴  Delete GITHUB_TOKEN?                              │
│                                                       │
│  This will remove the secret from all environments.  │
│                                                       │
│  ⚠ 2 agents currently use this secret:              │
│     • Reviewer Agent                                  │
│     • Deploy Bot                                      │
│  Those agents may fail or stall until a new token    │
│  is configured.                                       │
│                                                       │
│  [Cancel]                        [Delete Secret]      │
└───────────────────────────────────────────────────────┘
```

**Rules:**
- "[Delete Secret]" button is styled red/destructive, requires one click (not double confirmation — inline context is sufficient).
- If 0 agents use the secret, omit the warning block.
- After delete: row animates out (fade + height collapse, 200ms). Toast: "GITHUB_TOKEN removed."
- Undo: Toast includes "[Undo]" link for 5 seconds. After 5s, deletion is committed to backend.

---

## 1.7 Search & Filter

**Search bar behavior:**
- Placeholder: "Filter secrets…"
- Real-time filter (no submit): matches against secret name, service group name
- Non-matching groups collapse entirely (not just their contents)
- Zero results state:

```
┌───────────────────────────────────────────────────┐
│                                                   │
│             No secrets match "stripe"             │
│     Add a new secret for a custom service?        │
│                    [+ Add Secret]                 │
│                                                   │
└───────────────────────────────────────────────────┘
```

**Service filter dropdown:** "All services" | Anthropic | OpenRouter | GitHub | OpenAI | Groq | Langfuse | Other

**Status filter dropdown:** "Any status" | Valid | Stale | Invalid | Missing

---

## 1.8 Empty State (New User)

```
┌───────────────────────────────────────────────────────────┐
│                                                           │
│              🔑                                           │
│                                                           │
│         No secrets configured yet                        │
│                                                           │
│  Add your API keys to enable agents to call external     │
│  services. Keys are encrypted and never logged.          │
│                                                           │
│  Common keys to start with:                              │
│  • ANTHROPIC_API_KEY  — powers AI agents                 │
│  • GITHUB_TOKEN       — for code review & deploy agents  │
│  • OPENROUTER_API_KEY — alternative model routing        │
│                                                           │
│                  [Add Your First Secret]                  │
│                                                           │
└───────────────────────────────────────────────────────────┘
```

---

## 1.9 Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `G S` | Open Settings drawer |
| `Escape` | Close drawer (if no unsaved changes) |
| `Escape` | If unsaved changes: show "Discard changes?" inline prompt |
| `Cmd/Ctrl + F` | Focus search bar when drawer is open |
| `Cmd/Ctrl + Enter` | Submit active form (Add/Edit secret) |
| `Tab` | Navigate between form fields |
| `Shift + Tab` | Navigate backwards |

---

---

# 2. Onboarding / Deploy Interception Flow

## 2.1 Overview

This flow intercepts every LangGraph agent deploy (from template or custom) and validates that required secrets are present **before** any infrastructure is provisioned. The goal: eliminate the "infinite Starting… spinner" failure mode.

### Required Secrets by Agent Type

The backend config system uses env vars to determine which model/service is active. The pre-deploy check resolves required secrets from the workspace's `config.yaml`:

| Config value | Required Secret(s) |
|---|---|
| `anthropic:*` | `ANTHROPIC_API_KEY` |
| `openrouter:*` | `OPENROUTER_API_KEY` |
| `openai:*` | `OPENAI_API_KEY` |
| `groq:*` | `GROQ_API_KEY` |
| GitHub skills | `GITHUB_TOKEN` |
| Langfuse tracing | `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST` |
| Temporal workflows | `TEMPORAL_HOST` (optional — gracefully degrades) |

---

## 2.2 Step A: Pre-Deploy Secret Check (System)

### When it fires
- User clicks "Deploy" on any agent template
- User clicks "Deploy" on a custom agent config
- System checks: are all required secrets for this agent's config present in the org secret store?

### Logic

```
deploy_requested(agent_config)
        │
        ▼
resolve_required_secrets(agent_config.model, agent_config.skills)
        │
        ▼
check_secret_store(required_secrets)
        │
        ├── ALL PRESENT + VALID  ──────────────────────► Step D (Happy Path)
        │
        ├── ALL PRESENT, SOME INVALID  ────────────────► Step B (Warning variant)
        │
        ├── SOME MISSING  ─────────────────────────────► Step B (Missing secrets modal)
        │
        └── ALL MISSING  ──────────────────────────────► Step B (Full blocked state)
```

**Timing:** Check is synchronous and must complete before any provisioning call is made. Target: <500ms (secret store lookup is a fast key-value check).

---

## 2.3 Step B: Missing Secrets — Interception Modal

### Wireframe: Missing Secrets Modal

```
┌─────────────────────────────────────────────────────────┐
│  Configure required secrets                        [✕]  │
│─────────────────────────────────────────────────────────│
│                                                         │
│  Before deploying "Reviewer Agent", you need to        │
│  configure 2 required API keys.                        │
│                                                         │
│  ANTHROPIC_API_KEY                          ✓ Saved    │
│  GITHUB_TOKEN                               ✗ Missing   │
│  ┌─────────────────────────────────────────────────┐   │
│  │ ghp_••••••••••••••••••••••••••••••              │   │
│  └─────────────────────────────────────────────────┘   │
│  [👁 Show]                                              │
│                                                         │
│  OPENROUTER_API_KEY                         ✗ Missing   │
│  ┌─────────────────────────────────────────────────┐   │
│  │                                                 │   │
│  └─────────────────────────────────────────────────┘   │
│  [👁 Show]                 [Test connection]            │
│                                                         │
│  ─────────────────────────────────────────────────     │
│  ⚠ These keys are stored encrypted and used only       │
│    by your agents. They are never logged.              │
│                                                         │
│  [Skip for now — deploy anyway]   [Save & Deploy →]    │
└─────────────────────────────────────────────────────────┘
```

### Modal Specifications

| Property | Value |
|---|---|
| Width | 560px |
| Trigger | Pre-deploy check returns missing/invalid secrets |
| Blocking | Yes — deploy is paused, not cancelled |
| Dismissible | Yes via [✕] or Escape — triggers "Skip" path |

### Field Design

- Each missing secret gets its own labelled password input
- Already-configured secrets show a `✓ Saved` badge (green) with no input — they don't need re-entry
- Invalid secrets (present but failed validation) show an amber `⚠ Invalid` badge + input pre-filled with masked value + "Clear to retype" affordance

### "Test Connection" Button

- Appears per-field when the field has a value entered
- Tests only that one secret in isolation
- States: idle → [◌ Testing…] → [✓ Connected] (2s auto-hide) or [✗ Failed — try another key]
- Testing one field does not block the other fields

### Validation Before "Save & Deploy"

- All missing fields must be non-empty
- At least one attempted test-connection per field is encouraged but not required (user can save untested keys)
- If user clicks "Save & Deploy" with empty required fields: fields turn red with "This field is required" inline error; button does not fire

### "Skip for now" Option

**Design intent:** Never hard-block deploys. Users may be testing, or keys may be injected via infrastructure (not the UI). Skipping is allowed but communicated clearly.

Clicking "Skip for now":
```
┌──────────────────────────────────────────────────┐
│ Are you sure?                                    │
│                                                  │
│ Deploying without GITHUB_TOKEN means this agent  │
│ may fail immediately. You can add the key later  │
│ in Settings → Secrets.                           │
│                                                  │
│ [Go back]              [Deploy without secrets]  │
└──────────────────────────────────────────────────┘
```
"Deploy without secrets" proceeds to Step D but with a banner warning (see section 2.5).

---

## 2.4 Step C: Error State — Secrets Still Missing After Deploy Attempt

### When this occurs
- User skipped secrets AND deploy fails due to missing auth
- User had invalid key that wasn't caught by client-side validation
- Backend preflight (`preflight.py::run_preflight`) returns an auth/config error

### Error State Wireframe: Agent Card on Canvas

```
┌─────────────────────────────────────────────────────┐
│  🔴  Reviewer Agent                                 │
│      Failed to start                                │
│─────────────────────────────────────────────────────│
│  GITHUB_TOKEN is missing or invalid.                │
│  This agent cannot authenticate to GitHub.          │
│                                                     │
│  [Configure Secrets]       [View Logs]   [Retry]    │
└─────────────────────────────────────────────────────┘
```

**This replaces the "Starting…" spinner entirely.**

### Error State Rules

| Trigger | Error Text Pattern |
|---|---|
| `ANTHROPIC_API_KEY` missing | "This agent requires an Anthropic API key to run." |
| `ANTHROPIC_API_KEY` invalid (401) | "The Anthropic API key is invalid or has expired." |
| `GITHUB_TOKEN` missing | "GITHUB_TOKEN is missing. This agent cannot access GitHub." |
| Generic auth failure | "Authentication failed. Check your API keys in Settings." |
| Multiple missing | "2 required secrets are missing: GITHUB_TOKEN, OPENROUTER_API_KEY." |

**Error state anatomy:**
- Red left border on agent card (4px)
- "Failed to start" subtitle replaces the status badge
- Inline error message (specific, actionable — no "Something went wrong")
- Three CTAs:
  - **[Configure Secrets]** — opens Settings drawer pre-filtered to this agent's required secrets
  - **[View Logs]** — opens log drawer showing preflight error output
  - **[Retry]** — re-runs preflight check (use after fixing secrets)

### Preventing the Infinite Spinner

**Spinner timeout rule:** Any agent stuck in "Starting…" for >30 seconds automatically transitions to this error state. The error message reads:

```
Took too long to start. This may be a missing secret 
or a configuration issue. Check [View Logs] for details.

[Configure Secrets]    [View Logs]    [Retry]
```

This is a catch-all safety net for edge cases the pre-deploy check misses.

---

## 2.5 Step D: Happy Path — All Secrets Present

### Deploy Progress Indicator

```
┌─────────────────────────────────────────────────────┐
│  🔵  Reviewer Agent                    [Deploying…] │
│─────────────────────────────────────────────────────│
│  ████████████████░░░░░░░░░░░░  Provisioning…       │
│  ✓ Secrets validated                               │
│  ✓ Config loaded                                   │
│  ◌ Starting runtime…                               │
└─────────────────────────────────────────────────────┘
```

**Progress steps (from backend bootstrap sequence):**

| Step | Source | Display text |
|---|---|---|
| 1 | pre-deploy check | "Secrets validated" |
| 2 | `load_config()` | "Config loaded" |
| 3 | `run_preflight()` | "Preflight checks passed" |
| 4 | `get_adapter()` | "Runtime selected: LangGraph" |
| 5 | `_common_setup()` | "Loading skills & plugins…" |
| 6 | A2A registration | "Registering agent…" |
| 7 | Heartbeat received | "Agent online" |

**Success state:**
```
┌─────────────────────────────────────────────────────┐
│  🟢  Reviewer Agent                        [Online] │
│      Ready · 0 active tasks                        │
└─────────────────────────────────────────────────────┘
```

### Skipped-Secrets Banner (when user chose "Deploy anyway")

If user skipped secrets but deploy succeeded anyway (key injected via infra):
- No banner needed once agent is 🟢 Online

If user skipped secrets and deploy is running but agent hasn't fully started:
```
┌─────────────────────────────────────────────────────┐
│  🟡  Reviewer Agent                                 │
│  ⚠ Missing secrets: GITHUB_TOKEN                   │
│  This agent may fail when it needs to access GitHub │
│  [Configure now]                                    │
└─────────────────────────────────────────────────────┘
```

---

## 2.6 Edge Cases

| Scenario | Handling |
|---|---|
| Only SOME keys missing | Show modal with checkmarks for present keys, inputs only for missing ones. Never ask user to re-enter a key they've already set. |
| Key exists but is invalid | Show `⚠ Invalid` badge instead of `✗ Missing`. Prompt: "This key failed validation. Re-enter or test it." |
| Langfuse keys missing | These are optional (tracing only). Separate them into a collapsible "Optional: Observability" section in the modal. Don't block deploy. |
| Temporal host missing | Optional — gracefully degrades. Don't surface in modal at all. |
| User has no permission to write secrets | Show: "You don't have permission to add secrets. Ask your org admin to add GITHUB_TOKEN, then retry." with [Retry] button. |
| Org has multiple environments (dev/prod) | Modal includes environment selector: "Adding to: [Production ▾]" |
| Secret store is unreachable | Treat as "skip" — show warning banner on agent card: "Could not verify secrets. Deploy proceeding — check your keys if the agent fails." |

---

---

# 3. Everything on UI — API-Only Feature Audit

## 3.1 Methodology

The following features are confirmed API-only based on codebase analysis. Each entry specifies:
- **Current state:** How it's done today
- **Proposed UI location:** Where in the canvas it should live
- **Interaction pattern:** How users interact with it
- **Priority:** P0 (blocks ship), P1 (high value, next sprint), P2 (nice to have)

---

## 3.2 Feature Inventory

---

### Feature 1: Global Secrets / API Key Management
**Priority: P0**

**Current state:** Environment variables injected at container startup. No UI exists.

**Proposed UI:** Settings drawer → Secrets panel (fully specced in Section 1 above).

**Gap summary:** Users deploying agents from templates have no way to provide required secrets without direct infrastructure access. This blocks non-technical users from using the product at all.

---

### Feature 2: Plugin Management (Install / Configure / Enable / Disable / Remove)
**Priority: P0**

**Current state:**
- Plugins are directories placed in `/configs/plugins/<name>/`
- Each plugin has a `plugin.yaml` manifest (name, version, skills, rules)
- No install mechanism exists in any UI — plugins are deployed by copying files to the server
- Hot-reload is supported: dropping a new plugin dir triggers automatic pickup

**Proposed UI location:** Settings drawer → "Plugins" tab (new nav section)

**Interaction pattern:**

```
┌─────────────────────────────────────────────────────────┐
│ Plugins                              [Browse Marketplace]│
│─────────────────────────────────────────────────────────│
│ INSTALLED                                               │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ 🔌 GitHub Integration          v1.2.0  [Enabled ▾]  │ │
│ │    Adds code review & PR management skills          │ │
│ │    Skills: review_pr, create_branch, merge_pr       │ │
│ │    [Configure]  [View rules]  [Disable]  [Remove]   │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ 🔌 Snyk Security Scanner       v0.9.1  [Disabled ▾] │ │
│ │    Static analysis & vulnerability scanning         │ │
│ │    [Enable]  [Remove]                               │ │
│ └─────────────────────────────────────────────────────┘ │
│                                                         │
│ AVAILABLE (from marketplace)                            │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ 🔌 Slack Notifications                   [Install]  │ │
│ └─────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

**Actions and behavior:**

| Action | Behavior |
|---|---|
| Install | POST plugin manifest + files to platform API; platform copies to `/configs/plugins/`; hot-reload picks it up |
| Enable | Moves plugin from disabled list to active; restarts affected agents (with confirmation if agents are active) |
| Disable | Removes plugin rules from agent system prompt on next heartbeat; skills marked unavailable |
| Configure | Slide-open sub-panel: shows plugin's configurable fields from `plugin.yaml` (if any) |
| Remove | DELETE call + confirmation dialog: "This will remove X skills from Y agents. Are you sure?" |
| View rules | Read-only view of `rules/*.md` files — so users understand what behavior the plugin adds |

**Restart impact warning:**
```
⚠ Enabling "GitHub Integration" will restart 2 active agents.
  Active tasks will be interrupted.
  [Cancel]     [Enable and restart agents]
```

---

### Feature 3: Organization Import
**Priority: P1**

**Current state:** Organizations (and their member workspaces) are defined in YAML configuration files. Import from external sources (GitHub orgs, existing configs) is done manually.

**Proposed UI location:** Top bar → Org switcher dropdown → "Import organization" option at bottom of list

**Interaction pattern: Wizard (3 steps)**

```
Step 1: Choose Import Source
┌─────────────────────────────────────────────────────┐
│  Import Organization                                │
│─────────────────────────────────────────────────────│
│  Where are you importing from?                      │
│                                                     │
│  ○ GitHub Organization                              │
│    Import members and repos from a GitHub org       │
│                                                     │
│  ○ YAML config file                                 │
│    Upload an existing workspace config              │
│                                                     │
│  ○ Another Starfire org                             │
│    Clone structure from a different organization    │
│                                                     │
│  [Cancel]                              [Next →]     │
└─────────────────────────────────────────────────────┘

Step 2: Configure Import
(varies by source — GitHub: enter org name + GITHUB_TOKEN;
 YAML: file upload drag-and-drop;
 Starfire: org selector)

Step 3: Preview & Confirm
┌─────────────────────────────────────────────────────┐
│  Review import                                      │
│─────────────────────────────────────────────────────│
│  Importing "acme-corp" will create:                 │
│  • 1 parent workspace (Coordinator)                 │
│  • 4 child workspaces                               │
│  • 12 skills                                        │
│  • 3 plugins                                        │
│                                                     │
│  [Back]                     [Import Organization]   │
└─────────────────────────────────────────────────────┘
```

---

### Feature 4: Agent Pause / Resume Controls
**Priority: P0**

**Current state:**
- Agents run continuously once deployed
- No pause/resume mechanism exists in any UI
- The only control is full teardown (delete workspace) or letting the agent idle
- The heartbeat system tracks `status: online` but has no `paused` state exposed to UI

**Proposed UI location:** Agent card on canvas (inline controls) + Agent detail panel

**Interaction pattern:**

**Agent Card Controls (visible on hover or as persistent icons for active agents):**
```
┌─────────────────────────────────────────────────────┐
│  🟢  Reviewer Agent                                 │
│      Online · 2 active tasks                       │
│                                                     │
│  [⏸ Pause]    [🔄 Restart]    [🗑 Remove]           │
└─────────────────────────────────────────────────────┘
```

**Pause flow:**
```
User clicks [⏸ Pause]
        │
        ▼
If agent has active tasks:
┌─────────────────────────────────────────────────────┐
│  Pause Reviewer Agent?                              │
│                                                     │
│  This agent has 2 active tasks. Pausing will        │
│  suspend execution. Tasks will resume when you      │
│  unpause.                                           │
│                                                     │
│  [Cancel]              [Pause (suspend tasks)]      │
└─────────────────────────────────────────────────────┘

If agent is idle:
        │  (no confirmation needed — immediate)
        ▼

Agent card transitions to:
┌─────────────────────────────────────────────────────┐
│  ⏸  Reviewer Agent                     [Paused]    │
│     Paused since 2:34 PM                           │
│                                                     │
│  [▶ Resume]    [🔄 Restart]    [🗑 Remove]          │
└─────────────────────────────────────────────────────┘
```

**Backend implication:** The platform API needs a `PATCH /workspaces/{id}/status` endpoint with `{"status": "paused" | "online"}`. The heartbeat loop should respect paused state and not spawn new tasks. This is a backend feature request that unblocks the UI.

---

### Feature 5: HITL (Human-in-the-Loop) Channel Configuration
**Priority: P1**

**Current state:**
- HITL channels configured in `config.yaml` under `hitl:` block
- Supported channels: dashboard (default), Slack (webhook URL), email (SMTP config)
- No UI to configure these — requires editing YAML directly

**Proposed UI location:** Settings drawer → "Notifications" tab (or within each agent's detail panel)

**Interaction pattern:**

```
┌─────────────────────────────────────────────────────┐
│ Approval Notifications                              │
│─────────────────────────────────────────────────────│
│ When an agent requests approval, notify via:       │
│                                                     │
│ ☑ Canvas dashboard  (always on)                    │
│                                                     │
│ ○ Slack                                             │
│   Webhook URL: ┌──────────────────────────────────┐ │
│                │ https://hooks.slack.com/...       │ │
│                └──────────────────────────────────┘ │
│   [Test]  [Save]                                    │
│                                                     │
│ ○ Email                                             │
│   ┌──────────────────┐  ┌──────────────────────┐   │
│   │ SMTP host        │  │ Port                 │   │
│   └──────────────────┘  └──────────────────────┘   │
│   ┌──────────────────────────────────────────────┐ │
│   │ From address                                 │ │
│   └──────────────────────────────────────────────┘ │
│   ┌──────────────────────────────────────────────┐ │
│   │ To address                                   │ │
│   └──────────────────────────────────────────────┘ │
│   [Test]  [Save]                                    │
└─────────────────────────────────────────────────────┘
```

---

### Feature 6: Memory Scope Configuration
**Priority: P2**

**Current state:**
- Memory operates at three scopes: LOCAL (per-workspace), TEAM (parent + siblings), GLOBAL (org-wide)
- No UI exists to view, search, or manage persisted memory across scopes
- Users cannot see what agents have "remembered" or correct wrong memories

**Proposed UI location:** Agent detail panel → "Memory" tab

**Interaction pattern:**
```
┌─────────────────────────────────────────────────────┐
│  Memory — Reviewer Agent                            │
│─────────────────────────────────────────────────────│
│ [Local ▾]  [🔍 Search memories…]                   │
│─────────────────────────────────────────────────────│
│ • "Project uses Python 3.11 with strict typing"     │
│   Saved 2026-04-07 · Local scope            [🗑]   │
│                                                     │
│ • "Do not merge PRs on Friday"                      │
│   Saved 2026-04-01 · Team scope             [🗑]   │
│                                                     │
│                    [Load more]                      │
└─────────────────────────────────────────────────────┘
```

Delete is an admin action (memory is otherwise append-only). Deleting a memory shows: "This memory will no longer be available to agents in this scope."

---

### Feature 7: Audit Log Viewer
**Priority: P1**

**Current state:**
- Audit events are written as JSON Lines to `/app/audit.log` via `tools/audit.py`
- Events include: action, actor, decision (allow/deny), RBAC role, timestamp
- No UI surfaces this log — it is only accessible via SSH/file system

**Proposed UI location:** Settings drawer → "Audit Log" tab

**Interaction pattern:**
```
┌─────────────────────────────────────────────────────┐
│ Audit Log                                           │
│─────────────────────────────────────────────────────│
│ [🔍 Search…]  [Date range ▾]  [Action type ▾]     │
│─────────────────────────────────────────────────────│
│ 2026-04-09 14:32  ALLOW  delete_branch             │
│   Actor: Reviewer Agent · Role: developer           │
│   "Deleted branch feature/auth-refactor"   [Details]│
│                                                     │
│ 2026-04-09 14:28  DENY   push_to_main              │
│   Actor: Deploy Bot · Role: developer               │
│   "Attempted force push — blocked by policy" [Details]│
└─────────────────────────────────────────────────────┘
```

---

### Feature 8: RBAC Role Assignment
**Priority: P1**

**Current state:**
- RBAC roles defined per workspace in `config.yaml` under `rbac:` block
- Roles: `developer`, `admin`, `readonly`
- Role governs which agent actions are allowed (enforced in `tools/audit.py`)
- No UI to view or change roles — YAML only

**Proposed UI location:** Settings drawer → "Organization" tab → "Members & Roles" section

**Interaction pattern:**
```
┌─────────────────────────────────────────────────────┐
│ Agent Roles                                         │
│─────────────────────────────────────────────────────│
│ AGENT               ROLE              ACTIONS       │
│ Reviewer Agent      [Developer ▾]     ...           │
│ Deploy Bot          [Admin ▾]         ...           │
│ Docs Writer         [Read Only ▾]     ...           │
│─────────────────────────────────────────────────────│
│ Role ▾ controls what actions agents are permitted   │
│ to take. Admin agents can modify org settings.      │
└─────────────────────────────────────────────────────┘
```

Role changes take effect on next agent task (no restart required — roles are checked at action time in `audit.py`).

---

### Feature 9: Skill Hot-Reload Status & Management
**Priority: P2**

**Current state:**
- Skills are watched for changes by `skills/watcher.py`
- Reload events fire when skill files change in `/configs/skills/`
- No UI shows which skills are currently loaded, whether they loaded successfully, or which failed

**Proposed UI location:** Agent detail panel → "Skills" tab

**Interaction pattern:**
```
┌─────────────────────────────────────────────────────┐
│ Skills — Reviewer Agent                  [+ Add]    │
│─────────────────────────────────────────────────────│
│ 🟢 review_pr      Loaded · 3 tools                 │
│ 🟢 create_branch  Loaded · 1 tool                  │
│ 🔴 deploy         Error loading: ImportError in     │
│                   tools/deploy.py:14   [View error] │
│─────────────────────────────────────────────────────│
│ Last reloaded: 14:32                   [Reload all] │
└─────────────────────────────────────────────────────┘
```

---

### Feature 10: Telemetry / Tracing Configuration
**Priority: P2**

**Current state:**
- OpenTelemetry tracing configured via env vars: `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_SERVICE_NAME`
- Langfuse tracing configured via `LANGFUSE_*` vars
- No UI to enable/disable or point to a different collector

**Proposed UI location:** Settings drawer → "Observability" tab

Simple toggle + endpoint field. Lower priority as this is primarily a DevOps concern.

---

## 3.3 Priority Summary

| # | Feature | Priority | Effort | Notes |
|---|---|---|---|---|
| 1 | Global Secrets CRUD | P0 | M | Fully specced in Section 1 |
| 4 | Agent Pause/Resume | P0 | M | Needs backend `PATCH /status` endpoint |
| 2 | Plugin Management | P0 | L | Needs plugin marketplace API |
| 7 | Audit Log Viewer | P1 | S | Backend already writes logs |
| 8 | RBAC Role Assignment | P1 | S | Reads/writes config.yaml |
| 5 | HITL Channel Config | P1 | M | Reads/writes config.yaml hitl block |
| 3 | Organization Import | P1 | L | Wizard UI + new import API |
| 6 | Memory Management | P2 | M | Needs search API endpoint |
| 9 | Skill Status & Mgmt | P2 | S | Watcher already tracks state |
| 10 | Telemetry Config | P2 | S | Toggle + env var write |

**Effort key:** S = Small (1-2 days) · M = Medium (3-5 days) · L = Large (1-2 weeks)

---

## 3.4 Navigation Architecture: Where Does Everything Live?

```
Top Bar
├── [Logo]  [Breadcrumb]  [Search]  [Notifications 🔔]  [Settings ⚙]  [Avatar]
│
└── Settings Drawer (⚙)
    ├── Secrets & API Keys  ← P0 (Section 1)
    ├── Plugins             ← P0 (Feature 2)
    ├── Notifications       ← P1 (Feature 5: HITL channels)
    ├── Organization
    │   ├── Members & Roles ← P1 (Feature 8)
    │   └── Import          ← P1 (Feature 3)
    ├── Audit Log           ← P1 (Feature 7)
    ├── Observability       ← P2 (Feature 10)
    └── Danger Zone         (future: delete org, export data)

Agent Card (canvas)
├── [⏸ Pause]  [▶ Resume]  [🔄 Restart]  [🗑 Remove]  ← P0 (Feature 4)
└── Click to open Agent Detail Panel →
    ├── Overview (current task, uptime, error rate)
    ├── Skills              ← P2 (Feature 9)
    ├── Memory              ← P2 (Feature 6)
    └── Logs
```

---

*End of spec — UX Designer Agent · 2026-04-09*
