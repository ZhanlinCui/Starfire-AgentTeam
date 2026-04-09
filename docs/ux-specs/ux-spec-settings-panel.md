# UX Spec: Settings Panel — Global Secrets CRUD
**Version:** 1.0  
**Date:** 2026-04-09  
**Author:** UI/UX Designer Agent  
**Status:** Ready for Engineering Review

---

## 0. Design Decision: Slide-Over Panel vs Modal vs Dedicated Page

**Recommendation: Slide-Over Drawer (right-anchored, 480px wide)**

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| **Slide-over drawer** | Canvas stays visible; user retains spatial context; dismissible with Escape; standard settings pattern (Vercel, Linear, GitHub) | Slightly less vertical space than full page | **CHOSEN** |
| Modal (centered overlay) | Focused attention | Blocks canvas entirely; feels heavy for settings; no persistent reference to agent context | Rejected |
| Dedicated page | Maximum space | Loses canvas context; navigation overhead; feels disconnected from in-context workflow | Rejected |

**Rationale:** Users managing secrets often need to reference which agents are running (visible in the canvas behind the panel). The slide-over keeps context intact. The 480px width comfortably fits key name + masked value + actions in a single row without horizontal scroll.

---

## 1. Entry Point

### 1.1 Gear Icon Placement

```
┌──────────────────────────────────────────────────────────────────────────┐
│  [☁ Logo]  [Canvas Name ▾]          [+ New Agent]  [⚙]  [🔔]  [Avatar]  │
└──────────────────────────────────────────────────────────────────────────┘
```

- Position: **Right cluster of top bar**, between notification bell and user avatar
- Icon: Standard gear/cog (`⚙`, 20×20px)
- Tooltip on hover: `"Settings"` (300ms delay)
- Active state: Icon fills with accent color when panel is open
- Keyboard shortcut: `Cmd+,` (Mac) / `Ctrl+,` (Win/Linux) — industry-standard settings shortcut
- Shortcut hint shown in tooltip: `"Settings  ⌘,"`

### 1.2 Trigger Behavior

- Click or keyboard shortcut opens the panel with a 200ms ease-out slide animation from the right
- A semi-transparent backdrop overlay (`rgba(0,0,0,0.3)`) covers the canvas but does not intercept pointer events on the panel
- Focus moves immediately to the panel's first interactive element (search field if populated, otherwise "Add New Key" button)
- Clicking the backdrop or pressing `Escape` closes the panel (with save-guard: see §4.4)

---

## 2. Component Hierarchy

```
SettingsPanel (root)
├── PanelHeader
│   ├── PanelTitle ("Settings")
│   ├── TabBar
│   │   ├── Tab ("API Keys")          ← default active
│   │   └── Tab ("General")          ← future placeholder, greyed out
│   └── CloseButton (×)
│
├── PanelBody (scrollable)
│   ├── SearchBar                    ← shown when ≥4 secrets exist
│   │
│   ├── ServiceGroup [repeats per service]
│   │   ├── ServiceGroupHeader
│   │   │   ├── ServiceIcon          ← 20px logo (GitHub/Anthropic/OpenRouter)
│   │   │   ├── ServiceLabel         ← "GitHub", "Anthropic", "OpenRouter"
│   │   │   └── ServiceStatusBadge  ← "1 key", "2 keys", "No keys"
│   │   │
│   │   └── SecretRow [repeats per key in group]
│   │       ├── KeyNameLabel         ← e.g. "GITHUB_TOKEN"
│   │       ├── MaskedValueDisplay   ← "sk-••••••••••••abc1"
│   │       ├── RevealToggle         ← eye icon
│   │       ├── StatusIndicator      ← valid ✓ / invalid ✗ / unverified ○
│   │       ├── CopyButton           ← copies masked value (last 4 only; full value if revealed)
│   │       ├── EditButton           ← pencil icon, opens SecretEditForm inline
│   │       └── DeleteButton         ← trash icon, opens DeleteConfirmDialog
│   │
│   └── AddKeySection
│       ├── AddKeyButton             ← "+ Add API Key" (prominent, full-width)
│       └── AddKeyForm               ← expands inline on click (collapsed by default)
│           ├── ServiceSelector      ← dropdown: GitHub / Anthropic / OpenRouter / Custom
│           ├── KeyNameField         ← auto-filled from service selection, editable
│           ├── KeyValueField        ← password input, show/hide toggle
│           ├── ValidationHint       ← real-time format feedback
│           ├── TestConnectionButton ← optional; shown for supported services
│           └── FormActions
│               ├── SaveButton
│               └── CancelButton
│
├── EmptyState                       ← shown when no secrets exist (replaces ServiceGroups)
│   ├── EmptyIllustration
│   ├── EmptyTitle ("No API keys yet")
│   └── EmptyBody + AddFirstKeyButton
│
└── PanelFooter
    ├── KeyboardShortcutHint ("⌘, to open/close")
    └── DocsLink ("Learn about secrets →")
```

---

## 3. Wireframe Layouts

### 3.1 Panel — Populated State

```
┌─────────────────────────────────────────────────────┐
│  Settings                                    [×]     │
│  ┌──────────┬──────────┐                            │
│  │ API Keys │ General  │  ← TabBar                  │
│  └──────────┴──────────┘                            │
│                                                      │
│  🔍 Search keys...                                   │
│                                                      │
│  ── GitHub ────────────────────────────── 1 key ──  │
│                                                      │
│  GITHUB_TOKEN                                        │
│  ghp-••••••••••••••••••xK9f  [👁] [✓] [⎘] [✏] [🗑] │
│                                                      │
│  ── Anthropic ─────────────────────────── 1 key ──  │
│                                                      │
│  ANTHROPIC_API_KEY                                   │
│  sk-ant-••••••••••••••••a3Zq [👁] [○] [⎘] [✏] [🗑] │
│                                                      │
│  ── OpenRouter ─────────────────────────── 2 keys── │
│                                                      │
│  OPENROUTER_API_KEY                                  │
│  sk-or-••••••••••••••••7f1c  [👁] [✓] [⎘] [✏] [🗑] │
│                                                      │
│  OPENROUTER_API_KEY_STAGING                          │
│  sk-or-••••••••••••••••9d2a  [👁] [✗] [⎘] [✏] [🗑] │
│                                                      │
│  ┌────────────────────────────────────────────────┐ │
│  │  + Add API Key                                 │ │
│  └────────────────────────────────────────────────┘ │
│                                                      │
│  ⌘,  ·  Learn about secrets →                       │
└─────────────────────────────────────────────────────┘
```

Status indicator legend:
- `[✓]` green — verified valid via test connection
- `[✗]` red — failed connection test or invalid format
- `[○]` grey — not yet verified (saved but untested)

### 3.2 Panel — Empty State (New User)

```
┌─────────────────────────────────────────────────────┐
│  Settings                                    [×]     │
│  ┌──────────┬──────────┐                            │
│  │ API Keys │ General  │                            │
│  └──────────┴──────────┘                            │
│                                                      │
│                                                      │
│              🔑                                      │
│         No API keys yet                             │
│                                                      │
│    Add your API keys to let agents connect          │
│    to GitHub, Anthropic, OpenRouter, and more.      │
│                                                      │
│         [  + Add your first API key  ]              │
│                                                      │
│                                                      │
│  ⌘,  ·  Learn about secrets →                       │
└─────────────────────────────────────────────────────┘
```

### 3.3 Add Key Form — Expanded Inline

```
│  ── Add New Key ─────────────────────────────────── │
│                                                      │
│  Service                                            │
│  ┌─────────────────────────────────────────────┐   │
│  │ 🐙 GitHub                                 ▾ │   │
│  └─────────────────────────────────────────────┘   │
│                                                      │
│  Key name                                           │
│  ┌─────────────────────────────────────────────┐   │
│  │ GITHUB_TOKEN                                │   │
│  └─────────────────────────────────────────────┘   │
│                                                      │
│  Value                                              │
│  ┌──────────────────────────────────────┐  [👁]    │
│  │ ••••••••••••••••••••••••••••••••••  │          │
│  └──────────────────────────────────────┘          │
│  ⚠  Expected format: ghp_ or github_pat_           │
│                                                      │
│  [  Test connection  ]                              │
│                                                      │
│  [ Cancel ]                    [ Save key ]         │
└─────────────────────────────────────────────────────┘
```

### 3.4 Edit Mode — Inline on SecretRow

```
│  GITHUB_TOKEN                                        │
│  ┌──────────────────────────────────────┐  [👁]    │
│  │ ghp_•••••••••••••••••••••••••••••••  │          │
│  └──────────────────────────────────────┘          │
│  ✓ Valid format                                     │
│  [  Test connection  ]   [ Cancel ]  [ Save ]       │
```

- Row expands vertically; surrounding rows shift down
- Previous value pre-populated (masked)
- User must retype the full key to update (cannot edit in-place from masked)
- Hint text: `"Enter new value to replace — current value not shown for security"`

### 3.5 Delete Confirmation Dialog (Modal over panel)

```
┌──────────────────────────────────────────────────┐
│                                                    │
│  Delete "GITHUB_TOKEN"?                           │
│                                                    │
│  This key will be permanently removed. Agents     │
│  that depend on it may stop working:              │
│                                                    │
│  • Code Reviewer Agent                            │
│  • PR Automation Agent                            │
│                                                    │
│  This cannot be undone.                           │
│                                                    │
│  [ Cancel ]              [ Delete key ]           │
│                                                    │
└──────────────────────────────────────────────────┘
```

- "Delete key" button is red/destructive styled
- Dependent agent list fetched from platform at time of dialog open
- If no dependents: omit the list section, show simpler copy
- Confirm button is initially `disabled` for 1 second (prevents accidental double-click)

---

## 4. Interaction State Machine

### 4.1 Panel Lifecycle

```
[Closed]
   │  click ⚙ or ⌘,
   ▼
[Opening]  ── 200ms slide-in animation
   │
   ▼
[Idle / Browsing]
   │  
   ├── click Edit  ──────────────────────────► [Editing]
   │                                                │
   ├── click Add Key ──────────────────────────►  [Creating]
   │                                                │
   ├── click Delete ──────────────────────────► [Confirm Delete]
   │                                                │
   ├── Escape / click backdrop / click × ──────► [Closing]
   │                                               │
   └──────────────────────────────────────────────►▼
                                               [Closed]
```

### 4.2 Create Flow State Machine

```
[Idle]
   │  click "+ Add API Key"
   ▼
[Form Open — Empty]
   │  user selects service
   ▼
[Form Open — Service Selected]
   │  key name auto-filled; user types value
   ▼
[Form Open — Typing]
   │   ├── invalid format detected (real-time)
   │   │       ▼
   │   │  [Validation Error] ── shows inline hint ── user keeps typing ──► [Typing]
   │   │
   │   └── valid format
   │           ▼
   │      [Form Ready]
   │           │  optional: click "Test connection"
   │           ▼
   │      [Testing...] ── spinner on button, button disabled
   │           │
   │           ├── success ──► [Test Passed] — green checkmark, "Connected ✓"
   │           └── failure ──► [Test Failed] — red hint, "Invalid key or no permission"
   │
   │  click "Save key"
   ▼
[Saving] ── spinner, all fields disabled
   │
   ├── success ──► [Saved] ── toast "API key saved", row appears in list, form collapses
   └── error   ──► [Save Error] ── inline error banner "Failed to save. Try again."
```

### 4.3 Edit Flow State Machine

```
[Idle — SecretRow]
   │  click ✏ Edit
   ▼
[Edit Form Open] ── row expands, masked value shown, cursor in field
   │  user types new value
   ▼
[Typing — Edit]
   │   ├── invalid format ──► [Validation Error inline]
   │   └── valid format ──► [Edit Form Ready]
   │
   │  click "Save"
   ▼
[Saving Edit] ── spinner
   │
   ├── success ──► [Saved] ── row collapses, status badge resets to [○] unverified
   └── error   ──► [Save Error inline]
   
   (Escape or "Cancel" at any point) ──► [Idle — no changes]
```

### 4.4 Unsaved Changes Guard

If user attempts to close panel (×, Escape, backdrop click) while a form is open with unsaved input:

```
┌─────────────────────────────────────────┐
│  Discard unsaved changes?               │
│                                         │
│  [ Keep editing ]     [ Discard ]       │
└─────────────────────────────────────────┘
```

- Do NOT show this guard if the form is empty (user opened form but typed nothing)

### 4.5 Delete Flow State Machine

```
[Idle — SecretRow]
   │  click 🗑 Delete
   ▼
[Fetching dependents] ── brief spinner on row (≤500ms)
   │
   ▼
[Delete Confirm Dialog open]
   │
   ├── click "Cancel" ──► [Idle]
   │
   └── click "Delete key" (after 1s delay unlocks)
           ▼
       [Deleting] ── row fades to 50% opacity
           │
           ├── success ──► row removed with slide-up animation; toast "Key deleted"
           └── error   ──► row restores; toast "Failed to delete. Try again."
```

---

## 5. Key Masking Specification

| Scenario | Display Format | Example |
|---|---|---|
| GitHub PAT (classic) | `ghp_••••••••••••` + last 4 | `ghp_••••••••••••xK9f` |
| GitHub PAT (fine-grained) | `github_pat_••••••` + last 4 | `github_pat_••••••xK9f` |
| Anthropic key | `sk-ant-••••••••` + last 4 | `sk-ant-••••••••a3Zq` |
| OpenRouter key | `sk-or-•••••••••` + last 4 | `sk-or-•••••••••7f1c` |
| Generic/custom | `••••••••••••••` + last 4 | `••••••••••••••9d2a` |

**Reveal behavior:**
- Click 👁 eye icon: full value revealed for that row only
- Eye icon changes to 👁‍🗨 (strikethrough variant) to indicate revealed state
- Auto-hide after **30 seconds** of inactivity — countdown not shown (silent)
- Revealed state is **session-only** — re-opening panel always shows masked values
- Copy button: when masked, copies the full value server-side (not the masked string); when revealed, copies visible string

---

## 6. Validation Rules by Service

| Service | Key Name | Expected Format | Regex Pattern |
|---|---|---|---|
| GitHub | `GITHUB_TOKEN` | `ghp_` or `github_pat_` prefix, 40+ chars | `^(ghp_\|github_pat_)[A-Za-z0-9_]{36,}$` |
| Anthropic | `ANTHROPIC_API_KEY` | `sk-ant-` prefix | `^sk-ant-[A-Za-z0-9\-_]{90,}$` |
| OpenRouter | `OPENROUTER_API_KEY` | `sk-or-` prefix | `^sk-or-[A-Za-z0-9\-_]{40,}$` |
| Custom | user-defined name | Non-empty, printable ASCII | `.{1,}` |

**Real-time validation timing:**
- Begin validating after user pauses typing for **400ms** (debounced)
- Do not validate on every keystroke (avoid red state while user is mid-paste)
- Always validate on blur (field loses focus)

**Validation message placement:**
- Below the value field, in 12px caption text
- Error: red text + `⚠` icon — `"Expected format: sk-ant-..."`
- Valid: green text + `✓` — `"Valid format"`
- Neutral (not yet validated): no message shown

---

## 7. Test Connection Behavior

Supported services: GitHub, Anthropic, OpenRouter  
Not supported: Custom keys (button hidden)

**Button states:**

| State | Button Label | Appearance |
|---|---|---|
| Ready | "Test connection" | Secondary outline style |
| Loading | "Testing..." | Spinner + disabled |
| Success | "Connected ✓" | Green, auto-resets after 3s |
| Failure | "Test failed" | Red, auto-resets after 5s |

**On success:** Status badge for that row updates to `[✓]` valid  
**On failure:** Inline message below button: `"Could not verify key. Check it has the required permissions."` + link to service docs

**Test connection scope:** Tests read-access only (e.g., `GET /user` for GitHub, `GET /models` for Anthropic). Does not mutate any data.

---

## 8. Service Grouping and Extensibility

Services are defined in a static config that maps to group headers:

```
services:
  github:
    label: "GitHub"
    icon: github-logo.svg
    keyNames: ["GITHUB_TOKEN"]
    docsUrl: "https://docs.github.com/en/authentication/..."
  anthropic:
    label: "Anthropic"
    icon: anthropic-logo.svg
    keyNames: ["ANTHROPIC_API_KEY"]
    docsUrl: "https://docs.anthropic.com/..."
  openrouter:
    label: "OpenRouter"
    icon: openrouter-logo.svg
    keyNames: ["OPENROUTER_API_KEY"]
    docsUrl: "https://openrouter.ai/docs/..."
  custom:
    label: "Other"
    icon: key-generic.svg
    keyNames: []   ← catches all unrecognized key names
```

Keys not matching any known service fall into an **"Other"** group at the bottom.

---

## 9. Search / Filter (≥4 secrets)

Search bar appearance threshold: shown only when 4+ secrets exist (avoid clutter for small sets).

**Behavior:**
- Filters `KeyNameLabel` text, case-insensitive, on every keystroke (no debounce needed — client-side)
- Matching characters **highlighted** in the key name
- If a service group has all keys filtered out, the group header is hidden
- If search yields 0 results: show inline `"No keys match 'xyz'"` message with "Clear search" link
- `Escape` clears search field and returns to full list (does not close panel)

**Keyboard shortcut:** `Cmd+F` / `Ctrl+F` while panel is open focuses the search field

---

## 10. Error States Summary

| Trigger | Error Location | Message | Recovery Action |
|---|---|---|---|
| Save fails (network) | Inline below form | "Failed to save. Check your connection and try again." | Retry button |
| Save fails (server 4xx) | Inline below form | "Could not save key. It may already exist with that name." | Edit name |
| Delete fails | Toast (top-right) | "Failed to delete key. Try again." | Row restored |
| Test connection 401 | Below test button | "Invalid key — permission denied." | Edit key value |
| Test connection 403 | Below test button | "Key valid but missing required scopes." | Link to service docs |
| Test connection timeout | Below test button | "Connection timed out. Service may be down." | Retry |
| Panel load fails | Full panel error state | "Couldn't load your API keys. Refresh to try again." | Refresh button |

---

## 11. Accessibility Specification

### 11.1 Keyboard Navigation

| Key | Action |
|---|---|
| `Tab` / `Shift+Tab` | Navigate between interactive elements |
| `Enter` / `Space` | Activate focused button |
| `Escape` | Close panel (with unsaved-guard if needed); collapse open form; clear search |
| `Cmd+,` / `Ctrl+,` | Toggle panel open/closed |
| `Cmd+F` / `Ctrl+F` | Focus search field when panel is open |
| `Arrow Up/Down` | Navigate service group rows (when focus is on a row, not inside a form) |

### 11.2 ARIA Roles and Labels

```html
<!-- Panel root -->
<aside role="dialog" aria-modal="false" aria-label="Settings: API Keys">

<!-- Tab bar -->
<div role="tablist">
  <button role="tab" aria-selected="true" aria-controls="panel-api-keys">API Keys</button>
  <button role="tab" aria-selected="false" aria-controls="panel-general">General</button>
</div>

<!-- Secret row -->
<div role="row" aria-label="GITHUB_TOKEN — GitHub — verified">
  <button aria-label="Toggle reveal GITHUB_TOKEN">👁</button>
  <button aria-label="Copy GITHUB_TOKEN to clipboard">⎘</button>
  <button aria-label="Edit GITHUB_TOKEN">✏</button>
  <button aria-label="Delete GITHUB_TOKEN">🗑</button>
</div>

<!-- Status indicator -->
<span role="status" aria-label="Connection status: verified">✓</span>

<!-- Live region for toasts -->
<div aria-live="polite" aria-atomic="true" class="toast-region" />
```

### 11.3 Focus Management

- **Open panel:** Focus moves to first interactive element (search field or Add button)
- **Close panel:** Focus returns to gear icon in top bar
- **Open edit form:** Focus moves to value input field
- **Submit/cancel form:** Focus returns to the Edit button for that row
- **Delete confirmation dialog:** Focus trapped within dialog; returns to row (or next row) on dismiss
- **Toast notifications:** Announced via `aria-live="polite"` region; do not steal focus

### 11.4 Color and Contrast

- Status badges must not rely on color alone: use icons + color (`✓` green, `✗` red, `○` grey)
- All text meets WCAG AA contrast (4.5:1 for normal text, 3:1 for large text)
- Focus rings: 2px solid `#0066CC` (or design system accent), offset 2px
- Error states: red border on input + `⚠` icon + descriptive text (not just color change)

### 11.5 Reduced Motion

- Slide-in animation: respects `prefers-reduced-motion` — if set, panel appears instantly (no slide)
- Row deletion animation: fade only (no slide-up) under reduced motion

---

## 12. Edge Cases

| Scenario | Behavior |
|---|---|
| Same key name added twice | Server returns 409; inline error "A key named X already exists. Edit it instead." with link to scroll to existing key |
| Very long key name (>60 chars) | Truncated with `…` in row label; full name shown on hover tooltip and in edit form |
| Pasting a key with leading/trailing whitespace | Value field auto-trims on paste; show hint "Whitespace was removed" |
| Key value contains newlines (multi-line secret) | Textarea shown instead of input; masking applies to all lines |
| No internet connection | Save/test actions disabled with tooltip "No connection"; panel content shown from last fetch |
| 0 dependent agents on delete | Skip the dependent list in confirm dialog; show "No agents currently use this key." |
| 50+ secrets (large org) | Search bar always shown (override the ≥4 threshold); virtual scrolling for rows |
| Session expires while panel open | Next API call returns 401; show inline banner "Session expired — [Re-authenticate]" |
| User lacks write permission (read-only role) | Edit/Delete/Add buttons replaced with lock icon; tooltip "You have read-only access" |

---

## 13. Responsive Behavior

| Viewport | Panel Behavior |
|---|---|
| Desktop (≥1024px) | 480px slide-over, canvas visible behind |
| Tablet (768–1023px) | 100% viewport width slide-over, canvas hidden |
| Mobile (<768px) | Full-screen bottom sheet; not primary use case but must be accessible |

---

*End of Settings Panel UX Spec v1.0*
