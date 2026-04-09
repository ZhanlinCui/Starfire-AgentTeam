# Canvas UI/UX Spec — Settings Panel & Onboarding Interception Flow

**Author:** UI/UX Designer Agent  
**Date:** 2026-04-09  
**Status:** Draft for Engineering Handoff  

---

## PRIORITY 1: Settings Panel — Global Secrets CRUD

---

### 1.1 Entry Point & Placement Rationale

**Location:** Top bar, far right — between the notification bell and user avatar.

```
┌─────────────────────────────────────────────────────────────────────────┐
│  ◈ Starfire Canvas     [Workspace Name ▾]          🔔  ⚙  [Avatar ▾]  │
└─────────────────────────────────────────────────────────────────────────┘
```

**Rationale for right-side placement:**
- Settings is a low-frequency, high-stakes action (not part of the agent-building flow). Rightward placement follows established SaaS convention (GitHub, Vercel, Linear) and keeps the left/center canvas area uncluttered.
- The gear sits between bell (notifications, ephemeral) and avatar (account/profile, personal) — a natural middle ground for "system configuration."
- Do **not** place it in a left sidebar or hamburger menu — secrets management is a first-class action that needs to be discoverable without hunting.

**Keyboard shortcut:** `⌘ ,` (Cmd+Comma) — universal convention for app preferences. Show tooltip on hover: `Settings  ⌘,`

---

### 1.2 Panel Type Decision: Slide-Over, Not Modal

**Decision: Right-side slide-over drawer (400px wide, full viewport height)**

| Criterion | Slide-Over | Modal | Dedicated Page |
|---|---|---|---|
| Canvas remains visible | ✅ User keeps context | ❌ Blocked | ✅ |
| Perceived weight | Light, reversible | Heavy, interruptive | Very heavy |
| Suitable for CRUD lists | ✅ | ❌ Cramped | ✅ |
| Close via Escape / backdrop | ✅ | ✅ | ❌ |
| Deep-links / shareability | ❌ | ❌ | ✅ |
| User expectation match | ✅ Settings panels | ❌ Alerts/confirmations | ✅ Dedicated admin tools |

**Why not modal:** Modals communicate "decide something urgent." Secrets management is deliberate, non-urgent, and may involve reading multiple values — a modal forces the user to commit or cancel rather than browse. Modals also block canvas, removing spatial context.

**Why not dedicated page:** Navigating away from the canvas to manage keys is disorienting and adds friction. The slide-over keeps the user grounded in their workspace while making changes.

**Dismissal:** Clicking outside the drawer, pressing `Escape`, or clicking the X closes without saving any in-progress edits (with a discard-confirmation if edits are dirty).

---

### 1.3 Component Hierarchy

```
<SettingsDrawer>                         # Slide-over container (root)
  <DrawerHeader>
    <DrawerTitle>Settings</DrawerTitle>
    <DrawerCloseButton />                 # ×, Escape also closes
  </DrawerHeader>

  <DrawerNav>                             # Left tab rail (future-proofed)
    <NavTab active>Secrets & Keys</NavTab>
    <NavTab disabled>Team</NavTab>        # P2 placeholder, greyed out
    <NavTab disabled>Billing</NavTab>     # P2 placeholder
  </DrawerNav>

  <DrawerBody>
    <SecretsPanel>                        # The active tab content

      <SectionHeader>
        <SectionTitle>API Keys & Secrets</SectionTitle>
        <AddSecretButton />               # "+ Add Secret" CTA
      </SectionHeader>

      <SearchBar />                       # Filter secrets by name/service

      <SecretGroupList>
        <SecretGroup service="anthropic">
          <ServiceHeader>
            <ServiceIcon src="anthropic.svg" />
            <ServiceName>Anthropic</ServiceName>
          </ServiceHeader>
          <SecretRow key="ANTHROPIC_API_KEY">
            <SecretName>ANTHROPIC_API_KEY</SecretName>
            <SecretValueMasked />         # "sk-ant-...c4f2"
            <RevealToggleButton />        # Eye icon
            <StatusBadge />              # Valid / Invalid / Unverified
            <SecretActionMenu>
              <MenuItem>Edit</MenuItem>
              <MenuItem>Test Connection</MenuItem>
              <MenuItem danger>Delete</MenuItem>
            </SecretActionMenu>
          </SecretRow>
        </SecretGroup>

        <SecretGroup service="github">…</SecretGroup>
        <SecretGroup service="openrouter">…</SecretGroup>
        <SecretGroup service="custom">…</SecretGroup>

        <EmptyState />                   # Shown when no secrets exist
      </SecretGroupList>

    </SecretsPanel>
  </DrawerBody>

  <!-- Portaled overlays (render above drawer) -->
  <AddEditSecretModal />                 # CREATE / UPDATE form
  <DeleteConfirmationModal />            # Danger confirmation
  <TestConnectionToast />               # Success/failure inline notification
</SettingsDrawer>
```

---

### 1.4 Wireframe — Secrets Panel (ASCII)

```
┌──────────────────────────────────────────┐
│ ⚙ Settings                            ×  │
├────────────┬─────────────────────────────┤
│ ● Secrets  │  API Keys & Secrets         │
│   & Keys   │                   [+ Add]   │
│            │  ┌─────────────────────┐    │
│ ○ Team     │  │ 🔍 Search secrets…  │    │
│   (soon)   │  └─────────────────────┘    │
│            │                             │
│ ○ Billing  │  ANTHROPIC                  │
│   (soon)   │  ──────────────────────     │
│            │  ANTHROPIC_API_KEY          │
│            │  sk-ant-...c4f2  👁  ● ···  │
│            │                             │
│            │  GITHUB                     │
│            │  ──────────────────────     │
│            │  GITHUB_TOKEN               │
│            │  ghp_...X9k2  👁  ⚠ ···    │
│            │                             │
│            │  OPENROUTER                 │
│            │  ──────────────────────     │
│            │  OPENROUTER_API_KEY         │
│            │  sk-or-...7ab1  👁  ● ···  │
│            │                             │
│            │  ┄ No more secrets ┄        │
└────────────┴─────────────────────────────┘

Legend:  ● = Valid (green dot)
         ⚠ = Invalid / unverified (amber)
         ··· = Action menu trigger
         👁  = Reveal/hide toggle
```

---

### 1.5 CREATE Flow — "Add Secret" Form

Triggered by "+ Add Secret" button. Opens a **modal** (layered above the drawer).

**Why a modal here:** The add/edit action IS a discrete decision with a clear commit point ("Save"). Modal-within-drawer is the correct pattern — the drawer provides context, the modal captures the transactional input.

```
┌──────────────────────────────────────────┐
│  Add Secret                           ×  │
│                                          │
│  Service                                 │
│  ┌───────────────────────────────────┐   │
│  │ Select service…                ▾  │   │
│  └───────────────────────────────────┘   │
│  ○ Anthropic  ○ GitHub  ○ OpenRouter      │
│  ○ OpenAI     ○ Groq    ○ Custom…        │
│                                          │
│  Key Name                                │
│  ┌───────────────────────────────────┐   │
│  │ ANTHROPIC_API_KEY                 │   │  ← Auto-filled from service selection
│  └───────────────────────────────────┘   │
│  Custom keys: editable free-text field   │
│                                          │
│  Secret Value                            │
│  ┌───────────────────────────────────┐   │
│  │ ●●●●●●●●●●●●●●●●●●●●●●     👁   │   │
│  └───────────────────────────────────┘   │
│  ⚡ Real-time format validation below    │
│                                          │
│  [Test Connection]     [Cancel] [Save]   │
└──────────────────────────────────────────┘
```

**Service → Key Name mapping (pre-filled, user cannot rename standard keys):**

| Service | Pre-filled key name | Format hint |
|---|---|---|
| Anthropic | `ANTHROPIC_API_KEY` | Starts with `sk-ant-` |
| GitHub | `GITHUB_TOKEN` | Starts with `ghp_` or `github_pat_` |
| OpenRouter | `OPENROUTER_API_KEY` | Starts with `sk-or-` |
| OpenAI | `OPENAI_API_KEY` | Starts with `sk-` |
| Groq | `GROQ_API_KEY` | Starts with `gsk_` |
| Custom | User-defined (uppercase, underscores, no spaces) | None |

**Real-time validation rules:**

1. Format check fires on blur (not on each keystroke — avoids flickering while typing).
2. If format is recognizably wrong: amber inline error below field — `"Anthropic keys start with sk-ant-. Check for typos."` — never "Invalid format."
3. Empty submission blocked: Save button disabled until key name + value both non-empty.
4. Key name collision (same name already exists): inline warning — `"ANTHROPIC_API_KEY already exists. Saving will overwrite it."` — Save button stays enabled (overwrite is valid UX).

**"Test Connection" button behavior:**

- Appears after user has typed a value (not before — reduces confusion about what it does).
- Click triggers spinner inline within the button: `[Testing…]`
- On success: button becomes `[✓ Connected]` (green, non-clickable for 3s, then resets).
- On failure: `[✗ Failed — see details]` — expands an inline error block:
  ```
  Connection failed: 401 Unauthorized
  Your key was rejected. Check it wasn't revoked or copied with extra whitespace.
  ```
- Test Connection does NOT save the key. It only validates. Save is a separate action.

---

### 1.6 READ — Key Masking & Status

**Masking format:** Show first prefix + ellipsis + last 4 characters.

- `sk-ant-api03-...c4f2`
- `ghp_...X9k2`
- `sk-or-v1-...7ab1`

**Never** show full key in the list view, even transiently. Reveal is opt-in per row.

**Reveal toggle:** Eye icon (`👁`). Click toggles the single row to show plaintext for 30 seconds, then auto-masks. A subtle countdown badge (`👁 28s`) reminds the user the value is exposed. Screen readers announce: `"ANTHROPIC_API_KEY revealed. Will hide in 30 seconds."` Only one key revealed at a time — revealing a second auto-hides the first.

**Status indicators:**

| Status | Visual | Condition |
|---|---|---|
| Valid | Green dot `●` | Last connection test passed |
| Invalid | Red dot `●` | Connection test returned 401/403 |
| Unverified | Amber dot `⚠` | Never tested, or format check inconclusive |
| Expired | Grey dot `●` with strikethrough label | Token expiry date known and past |

Status is stored client-side (or backend) from the last test. It is NOT re-tested on every panel open — that would cause latency and quota consumption.

**Grouping:** Keys are always grouped by service with a visual separator and service wordmark/icon. Within a group, keys are alphabetical. Custom keys form their own group at the bottom labeled "Custom." Empty groups are hidden (not shown as empty headers).

---

### 1.7 UPDATE Flow

Triggered by "Edit" in the `···` action menu on a row.

- Re-uses the same Add Secret modal, pre-populated with:
  - Service (locked — cannot change service of an existing key without deleting + recreating)
  - Key name (locked for standard keys; editable for custom keys)
  - Value field: **empty** (never pre-fill with the existing secret value — security principle)
- Helper text below value field: `"Leave blank to keep the existing value unchanged."`
- On Save with blank value: no-op update (nothing changes). Backend receives no payload for that field.
- Test Connection available during edit.

**State machine for edit:**

```
[Row: idle]
    │  click "Edit"
    ▼
[Modal: open, prepopulated]
    │  user modifies value
    ▼
[Modal: dirty]
    ├─ click "Cancel" → [Discard confirm: "Discard changes?"] → [Modal: closed]
    ├─ click "Test Connection" → [Modal: testing] → back to [Modal: dirty]
    └─ click "Save" → [Modal: saving] → 
           ├─ success → [Modal: closed] + [Toast: "Key updated"] + [Row: status=Unverified]
           └─ error → [Modal: error inline] "Save failed: permission denied"
```

---

### 1.8 DELETE Flow

Triggered by "Delete" in the `···` action menu.

**Confirmation modal (never skip this):**

```
┌────────────────────────────────────────────┐
│  ⚠  Delete Secret?                      ×  │
│                                            │
│  You're about to delete:                   │
│  ANTHROPIC_API_KEY                         │
│                                            │
│  3 agents currently use this key:          │
│  • Research Agent                          │
│  • Code Review Bot                         │
│  • Data Analyst                            │
│                                            │
│  These agents will fail if they attempt    │
│  to call Anthropic after deletion.         │
│                                            │
│  Type the key name to confirm:             │
│  ┌──────────────────────────────────────┐  │
│  │                                      │  │
│  └──────────────────────────────────────┘  │
│                                            │
│           [Cancel]   [Delete Key]          │
│                       (red, disabled until │
│                        name typed)         │
└────────────────────────────────────────────┘
```

**Copy for the "Delete Key" button:** "Delete Key" — not "Confirm" or "Yes." The verb makes clear what the action is.

**Dependent agent count:** Backend must expose an endpoint returning which workspace configs reference a given secret name. If none, omit the warning block and show a simpler confirmation.

**After delete:** Row disappears with a slide-out animation. Toast: `"ANTHROPIC_API_KEY deleted."` with an `[Undo]` action available for 8 seconds (optimistic deletion — backend holds a soft-delete for 8s).

---

### 1.9 Empty State

**First-time user (zero secrets):**

```
┌──────────────────────────────────────────┐
│  API Keys & Secrets              [+ Add]  │
│                                          │
│         🔑                               │
│                                          │
│     No secrets configured yet.           │
│                                          │
│  Add your API keys to enable agents      │
│  to call external services like          │
│  Anthropic, GitHub, and OpenRouter.      │
│                                          │
│         [Add Your First Secret]          │
└──────────────────────────────────────────┘
```

**Search returns no results:**

```
│  No secrets match "LANGFUSE"             │
│  [Clear search]  or  [+ Add new secret]  │
```

---

### 1.10 Error States

| Scenario | Location | Copy |
|---|---|---|
| Save failed (network) | Inline in modal | "Couldn't save. Check your connection and try again." |
| Save failed (permission denied) | Inline in modal | "Permission denied. Contact your org admin." |
| Test connection timeout | Inline in modal | "Connection timed out. The service may be down." |
| Delete failed | Toast (error) | "Delete failed. Try again in a moment." |
| Panel fails to load secrets | In panel body | "Couldn't load secrets. [Retry]" |

---

### 1.11 Interaction State Machine (Full Panel)

```
PANEL_CLOSED
    │  ⚙ click / ⌘,
    ▼
PANEL_OPEN → LOADING
    │  data loads
    ▼
PANEL_IDLE
    ├─ click "+ Add Secret" → MODAL_ADD_OPEN
    ├─ click "Edit" on row → MODAL_EDIT_OPEN
    ├─ click "Delete" on row → MODAL_DELETE_OPEN
    ├─ type in search → PANEL_FILTERED
    ├─ click "Test Connection" (from row menu) → ROW_TESTING → ROW_TESTED
    └─ press Escape / click backdrop → PANEL_CLOSED (no dirty state)

MODAL_ADD_OPEN / MODAL_EDIT_OPEN
    └─ internal state machine: [OPEN → DIRTY → TESTING? → SAVING → SAVED/ERROR]
           └─ on close → PANEL_IDLE

MODAL_DELETE_OPEN
    ├─ Cancel → PANEL_IDLE
    └─ Confirm → DELETING → PANEL_IDLE (row removed) + TOAST
```

---

### 1.12 Accessibility

| Concern | Implementation |
|---|---|
| Drawer focus management | On open: focus moves to DrawerCloseButton. On close: focus returns to the gear icon that triggered it. |
| Focus trap | Tab key cycles only within the drawer while it's open. |
| Secret value field | `type="password"` with `autocomplete="off"`. Label: `"ANTHROPIC_API_KEY value"`. |
| Reveal toggle | `aria-label="Reveal ANTHROPIC_API_KEY"` / `"Hide ANTHROPIC_API_KEY"`. Live region announces auto-hide countdown. |
| Status badges | `aria-label="Status: Valid"` — never rely on color alone (add icon + text). |
| Delete confirmation input | `aria-label="Type ANTHROPIC_API_KEY to confirm deletion"`. `aria-required="true"`. |
| Error messages | `role="alert"` for inline form errors. Screen reader reads immediately on appearance. |
| Keyboard nav | Full tab order: DrawerClose → NavTabs → SearchBar → SecretRows → AddButton. Row actions accessible via `···` menu triggered by `Enter`/`Space`. |

---

## PRIORITY 2: Onboarding / Deploy Interception Flow

---

### 2.1 Context

When a user deploys a LangGraph agent from a template, the backend's `run_preflight()` will fail or the agent will crash immediately if required env vars (secrets) are absent. Currently this surfaces as an infinite "Starting…" spinner — the worst possible UX. This spec replaces that with a clear interception flow.

The interception happens **before** the provisioning call is made. A pre-flight API call checks required secrets, then either proceeds or routes the user through the key-entry modal.

---

### 2.2 Full State Machine

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         DEPLOY STATE MACHINE                            │
└─────────────────────────────────────────────────────────────────────────┘

[TEMPLATE_SELECTED]
    │  User clicks "Deploy" button on template card
    ▼
[PRE_FLIGHT_CHECK]  ── spinner: "Checking requirements…" (max 5s timeout)
    │
    ├─ Timeout → [ERROR: PRE_FLIGHT_TIMEOUT]
    │       Copy: "Couldn't check your configuration. Try deploying again."
    │       Action: [Retry] [Cancel]
    │
    ├─ All secrets present + valid
    │       ▼
    │   [DEPLOY_INITIATED] → see Happy Path below
    │
    ├─ All secrets present, but one or more unverified (status unknown)
    │       ▼
    │   [DEPLOY_INITIATED] → deploy proceeds with warning toast:
    │   "Deploying with unverified keys. Agent may fail if keys are invalid."
    │
    └─ One or more secrets MISSING
            ▼
        [MISSING_KEYS_MODAL: OPEN]
            │
            ├─ User enters all required keys → [VALIDATE_KEYS]
            │       │
            │       ├─ Format invalid → [MODAL: VALIDATION_ERROR]
            │       │       Stay in modal. Inline errors on fields.
            │       │       User corrects → [VALIDATE_KEYS]
            │       │
            │       ├─ Format valid → [SAVE_KEYS]
            │       │       │
            │       │       ├─ Save fails → [MODAL: SAVE_ERROR]
            │       │       │       Copy: "Couldn't save keys. Try again."
            │       │       │       [Retry Save] button
            │       │       │
            │       │       └─ Save succeeds → [DEPLOY_INITIATED]
            │       │
            │       └─ "Test first" user clicks Test Connection
            │               → [MODAL: TESTING] → [MODAL: TEST_RESULT]
            │               Test pass → stays in modal, user clicks Save & Deploy
            │               Test fail → inline error, stays in modal
            │
            └─ User clicks "Skip" or "Cancel"
                    ▼
                [TEMPLATE_SELECTED] — canvas restored
                Banner warning: "Deployment cancelled. Some required keys are missing."

[DEPLOY_INITIATED]
    │  Progress indicator appears (replaces "Deploy" button area)
    ▼
[PROVISIONING]  ── animated progress bar, stage labels (see §2.6)
    │
    ├─ Success → [AGENT_RUNNING]
    │       Canvas shows agent card with green status indicator
    │       Toast: "Agent deployed successfully."
    │
    ├─ Runtime secret error (key present but rejected at runtime)
    │       ▼
    │   [RUNTIME_AUTH_ERROR]  — see §2.5
    │
    └─ Provision timeout (> 90s)
            ▼
        [PROVISION_TIMEOUT_ERROR]  — see §2.5
```

---

### 2.3 Component Hierarchy — Missing Keys Interception Modal

```
<DeployInterceptModal>                    # Full-screen overlay, centered modal
  <ModalHeader>
    <ModalIcon type="warning" />          # Amber key icon, not a red X
    <ModalTitle>                          # "Before you deploy…" (not "Error")
    <ModalSubtitle>                       # "[Template Name] needs API keys to run."
  </ModalHeader>

  <ModalBody>
    <RequiredKeysList>                    # Only the MISSING keys, not all keys
      <RequiredKeyRow key="ANTHROPIC_API_KEY">
        <ServiceIcon />
        <KeyName>ANTHROPIC_API_KEY</KeyName>
        <KeyStatus>Missing</KeyStatus>    # Or "Invalid" if present but bad
        <SecretInput>                     # password field
          <FormatHint />                  # "Starts with sk-ant-"
          <ValidationError />             # Inline, appears on blur
        </SecretInput>
        <TestConnectionButton />
      </RequiredKeyRow>
      <RequiredKeyRow key="GITHUB_TOKEN">…</RequiredKeyRow>
    </RequiredKeysList>

    <AlreadyPresentKeysList>              # Collapsed by default
      <CollapsibleToggle>
        "2 keys already configured ▸"    # Expands to show masked existing keys
      </CollapsibleToggle>
    </AlreadyPresentKeysList>

    <PrivacyNote>
      "Keys are stored securely and never logged."
    </PrivacyNote>
  </ModalBody>

  <ModalFooter>
    <SkipLink>                           # Text link, not a button — de-emphasised
      "Skip for now (agent may fail)"
    </SkipLink>
    <SecondaryButton>Cancel</SecondaryButton>
    <PrimaryButton>Save & Deploy</PrimaryButton>
  </ModalFooter>
</DeployInterceptModal>
```

---

### 2.4 Microcopy — Every State

**Modal title and subtitle:**
> **Before you deploy…**
> *Research Agent* requires 2 API keys to run. Add them now or the agent won't start.

**When SOME keys already present (partial):**
> **Almost ready to deploy**
> *Research Agent* needs 1 more key. You've already configured 2 of 3 required keys.

**Key row — missing:**
> `ANTHROPIC_API_KEY` · **Missing**
> *Starts with* `sk-ant-`

**Key row — present but invalid (format passes, but prior test failed):**
> `GITHUB_TOKEN` · **Invalid** — last test failed
> Enter a new token to replace the existing one.

**Format validation error (inline, on blur):**
> "Anthropic keys start with `sk-ant-`. Check for extra spaces or missing characters."

**Test connection — loading:**
> Button: `Testing…` (spinner, disabled)

**Test connection — success:**
> Button: `✓ Connected` (green, 3s, then resets to "Test Connection")
> Inline note: "Connection verified. Ready to deploy."

**Test connection — failure:**
> Button: `✗ Failed`
> Inline: "Key rejected (401). It may be revoked or copied incorrectly."

**Save & Deploy — loading:**
> Button: `Saving…` (spinner, disabled)
> Modal stays open until save + provision start confirmed.

**Skip link tooltip (on hover):**
> "The agent will start but immediately fail if it needs this key."

**Cancel — confirmation (only if any field has been typed into):**
> "Discard the keys you entered? You can add them later in Settings."
> [Keep editing] [Discard & Cancel]

**Post-deploy success toast:**
> "Research Agent deployed. All keys verified and saved."

---

### 2.5 Error States (Replacing the Infinite Spinner)

**Current broken state:** Infinite "Starting…" spinner with no recovery path.

**Replacement — Runtime Auth Error:**

```
┌────────────────────────────────────────────────────────────┐
│  Agent card on canvas:                                     │
│                                                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Research Agent                            ● Failed  │  │
│  │                                                      │  │
│  │  ⚠ Authentication failed                             │  │
│  │  The Anthropic API rejected the key. The agent       │  │
│  │  could not start.                                    │  │
│  │                                                      │  │
│  │  [Update ANTHROPIC_API_KEY]         [Remove Agent]   │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────┘
```

"Update ANTHROPIC_API_KEY" opens the Settings drawer pre-navigated to that specific key's Edit modal — no hunting required.

**Provision Timeout Error (> 90s without heartbeat):**

```
│  Research Agent                            ● Timed out  │
│                                                         │
│  ⏱ Deployment timed out                                │
│  The agent didn't respond within 90 seconds.            │
│  This may be a temporary issue.                         │
│                                                         │
│  [Retry Deployment]          [View Logs]  [Remove]      │
```

**Provision timeout retry behavior:** Retry is a full re-run of the pre-flight → deploy flow. Not a blind resend of the original deploy request, which might have partially executed.

**Pre-flight timeout (checking secrets takes > 5s):**
Do NOT show this as an error state that blocks deployment. Show:
```
"Couldn't verify your keys. Deploy anyway?"
[Cancel]  [Deploy Without Checking]
```

This keeps power users unblocked while protecting normal users.

---

### 2.6 Happy Path — Progress Indicator

Replaces the undifferentiated "Starting…" spinner with meaningful stage labels:

```
┌──────────────────────────────────────────────────────────┐
│  Research Agent                                          │
│                                                          │
│  ████████████░░░░░░░░░░░░   45%                         │
│  Provisioning workspace…                                 │
│                                                          │
│  ✓ Keys verified                                         │
│  ✓ Workspace created                                     │
│  ⟳ Loading tools and plugins                            │
│  ○ Starting agent runtime                                │
│  ○ Registering with canvas                               │
└──────────────────────────────────────────────────────────┘
```

Stage labels (pulled from backend lifecycle events via heartbeat/activity endpoints):

1. `Keys verified` — pre-flight passed
2. `Workspace created` — provisioning call succeeded
3. `Loading tools and plugins` — adapter `_common_setup()` running
4. `Starting agent runtime` — LangGraph/Claude Code agent spinning up
5. `Registering with canvas` — first heartbeat received by platform

If any stage fails, stop the progress bar, highlight the failed stage in red, and show the error state for that stage inline.

---

### 2.7 Edge Cases

| Edge Case | Handling |
|---|---|
| User navigates away during MISSING_KEYS_MODAL | If fields have been edited: discard-confirm dialog. If untouched: silent dismiss. Deployment does not proceed. |
| Same key required by two templates deploying simultaneously | Both intercept modals can share the key entry — saving from one updates the global store, the second modal detects the key is now present and auto-fills (masked). |
| Key passes format check but fails at runtime (false positive validation) | Agent card shows RUNTIME_AUTH_ERROR state (§2.5). "Update key" CTA. |
| Template declares a required key with no known service prefix (custom key) | Intercept modal shows a generic text field, no format hint, no test connection button. |
| User has read-only role (cannot create secrets) | Intercept modal shows keys as required but input fields are disabled. Copy: "You don't have permission to add keys. Contact your admin." |
| Pre-flight check API is unavailable (500) | Fail open: show warning toast "Couldn't verify keys" and allow deploy to proceed. Do not block on a backend failure. |
| Key exists but is expired (expiry date known) | Status badge shows "Expired" in pre-flight results. Intercept modal shows the expired key row with copy: "This key expired on [date]. Enter a replacement." |
| Network drops mid-deploy after keys saved | Keys are persisted before deploy call is made. On reconnect: show last known provision state. Offer [Check Status] which polls backend. |
