# UX Spec: Onboarding / Deploy Interception Flow
**Version:** 1.0  
**Date:** 2026-04-09  
**Author:** UI/UX Designer Agent  
**Status:** Ready for Engineering Review  
**Companion spec:** `ux-spec-settings-panel.md`

---

## 0. Overview and Design Principles

**Problem:** When a user deploys a LangGraph agent from a template, the current flow
spins up a container even when required secrets are missing — resulting in an infinite
"Starting..." spinner with no recovery path. This destroys trust on first use.

**Solution:** Intercept before provisioning. Check required secrets synchronously
client-side (against cached secret keys list, not values), show a focused inline modal
to collect missing keys, then re-attempt deployment. Never show an indefinite spinner
without a timeout and clear recovery path.

**Design principles:**
1. **Don't redirect** — user stays in context (canvas), not bounced to a settings page
2. **Minimal friction** — only ask for what this specific template needs, not all secrets
3. **Reuse existing components** — the inline key form from the Settings Panel spec is
   lifted and dropped here (single source of truth for that UI)
4. **Every spinner has a timeout** — max 30s before transitioning to an error state
5. **Always give a recovery action** — no dead ends

---

## 1. Trigger Conditions

This flow activates when **all three** of the following are true:

1. User clicks "Deploy" or "Use template" on a LangGraph agent template card
2. The template manifest declares one or more `required_secrets`
3. One or more of those secrets are not present in the user's global secrets store

Template manifest shape (for reference):
```yaml
name: "GitHub PR Reviewer"
runtime: langgraph
required_secrets:
  - key: GITHUB_TOKEN
    service: github
    purpose: "Read pull requests and post review comments"
  - key: ANTHROPIC_API_KEY
    service: anthropic
    purpose: "Run the LLM that analyzes code"
optional_secrets:
  - key: OPENROUTER_API_KEY
    service: openrouter
    purpose: "Fallback model if Anthropic is unavailable"
```

The pre-provision check compares `required_secrets[].key` against the list of key
**names** stored in the platform (values never leave the server). This check is
synchronous and must resolve in < 200ms (it's a key-name lookup, not a validation call).

---

## 2. Full State Machine

```
╔══════════════════════════════════════════════════════════════════════╗
║                    DEPLOY INTERCEPTION FLOW                          ║
╚══════════════════════════════════════════════════════════════════════╝

[CANVAS — Browsing Templates]
         │
         │  user clicks "Deploy" / "Use template"
         ▼
[CHECKING SECRETS]  ←── client-side, ~200ms
         │
         ├─── All required secrets present ──────────────────────────────────►─┐
         │                                                                       │
         ├─── Some or all secrets missing ──────────────────────────────────►─┐ │
         │                                                                    │ │
         │                                                                    ▼ │
         │                                              [MISSING KEYS MODAL — OPEN]
         │                                                         │
         │                    user fills in keys                   │
         │                    (one or more)                        │
         │                         │                               │
         │                         ▼                               │
         │                   [VALIDATING FORMAT]  ← client-side    │
         │                         │                               │
         │                    ┌────┴───────┐                       │
         │                 invalid       valid                      │
         │                    │             │                       │
         │                    ▼             ▼                       │
         │            [INLINE VALIDATION  [SAVING KEYS]            │
         │              ERROR — stay in   spinner on               │
         │              modal, re-edit]   Save btn                 │
         │                                   │                     │
         │                              ┌────┴──────┐              │
         │                           error        success          │
         │                              │             │            │
         │                              ▼             ▼            │
         │                       [SAVE ERROR      [KEYS SAVED]    │
         │                         inline]        toast ✓         │
         │                                           │             │
         │                                           │  ◄──────────┘
         │                                           │  (all keys now present)
         │                                           │
         │   ◄────────────── user cancels ───────────┤
         │   (cancel path — see §2.2)                │
         │                                           ▼
         └───────────────────────────────────► [PROVISIONING]
                                                     │
                                              30s timeout ─────────────────────►─┐
                                                     │                            │
                                               ┌─────┴──────┐                    │
                                          error            success                │
                                             │                │                   │
                                             ▼                ▼                   ▼
                                    [PROVISION ERROR]   [AGENT RUNNING]  [PROVISION TIMEOUT]
                                         │                    │                   │
                                  ┌──────┴──────┐            END          ┌──────┴──────┐
                              missing       other                      [RETRY?]    [Open Support]
                              secrets       error                          │
                                │             │                     user clicks retry
                                ▼             ▼                            │
                        [RUNTIME SECRET  [ERROR BANNER                     ▼
                          ERROR MODAL]   + Contact                  [PROVISIONING]  (loop, max 2x)
                              │          Support link]
                              │
                     (reuses Missing Keys Modal
                      with "Runtime error" framing)
```

### 2.1 State Definitions

| State | Description | Max Duration |
|---|---|---|
| `CHECKING_SECRETS` | Client fetches user's secret key names list and diffs against template manifest | 200ms |
| `MISSING_KEYS_MODAL` | User sees modal listing missing keys; enters values | No timeout (user action) |
| `VALIDATING_FORMAT` | Client-side regex validation against service format rules | Instant |
| `SAVING_KEYS` | POST to platform secrets API for each new key | 3s per key |
| `KEYS_SAVED` | All keys persisted; brief confirmation before auto-advancing | 1.5s (auto-advance) |
| `PROVISIONING` | Container spinning up; animated progress indicator | 30s max |
| `AGENT_RUNNING` | Agent is live; canvas shows live node | Terminal |
| `PROVISION_ERROR` | Container failed to start; classified into subcategories | Terminal (awaits user) |
| `PROVISION_TIMEOUT` | 30s elapsed without heartbeat | Terminal (awaits user) |
| `RUNTIME_SECRET_ERROR` | Agent started but immediately reports missing/invalid key | Terminal (awaits user) |

### 2.2 Cancel Path (from MISSING_KEYS_MODAL)

```
[MISSING_KEYS_MODAL]
    │  user clicks "Cancel" or presses Escape
    ▼
[CANCEL GUARD — if any value typed]
    ┌──────────────────────────────────────┐
    │  Discard and cancel deployment?      │
    │  Your entered keys won't be saved.   │
    │  [ Keep editing ]  [ Cancel deploy ] │
    └──────────────────────────────────────┘
    │
    ├── "Keep editing" → back to [MISSING_KEYS_MODAL]
    │
    └── "Cancel deploy" → modal closes
            │
            ▼
    [TEMPLATE CARD — DEPLOY CANCELLED STATE]
        ┌────────────────────────────────────────┐
        │  ⚠ Deployment cancelled                │
        │  Missing keys: GITHUB_TOKEN,           │
        │  ANTHROPIC_API_KEY                     │
        │  [Add keys in Settings]  [Try again]   │
        └────────────────────────────────────────┘
        Warning persists until user navigates away or clicks dismiss (×)
```

---

## 3. Component Hierarchy

```
DeployInterceptionModal (root)
├── ModalHeader
│   ├── TemplateIcon (24px service logo or generic robot icon)
│   ├── ModalTitle                    ← dynamic, see §5 copy
│   ├── ModalSubtitle
│   └── CloseButton (×)              ← triggers cancel guard if dirty
│
├── TemplateContextBanner            ← always visible at top of modal
│   ├── TemplateName ("GitHub PR Reviewer")
│   └── TemplateDescription (one-liner from manifest)
│
├── ModalBody
│   ├── MissingKeysList              ← shown in initial state
│   │   └── MissingKeyItem [repeats] ← one per missing required_secret
│   │       ├── ServiceIcon (20px)
│   │       ├── KeyName ("GITHUB_TOKEN")
│   │       ├── PurposeHint          ← from manifest: "Read pull requests..."
│   │       └── StatusDot            ← empty circle (not yet entered)
│   │
│   ├── KeyEntrySection              ← one per missing key, stacked vertically
│   │   └── KeyEntryField [repeats]
│   │       ├── FieldLabel           ← "GITHUB_TOKEN"
│   │       ├── ServiceHint          ← "GitHub Personal Access Token"
│   │       ├── ValueInput           ← password field, reveal toggle
│   │       │   └── RevealToggle
│   │       ├── ValidationHint       ← real-time format feedback (reused from Settings Panel)
│   │       ├── GetKeyLink           ← "Get a GitHub token →" (opens in new tab)
│   │       └── TestConnectionButton ← optional, per-service
│   │
│   ├── OptionalKeysDisclosure       ← collapsed by default
│   │   ├── DisclosureToggle ("Also add optional keys ▾")
│   │   └── OptionalKeyEntrySection  ← same structure as KeyEntrySection
│   │
│   └── PartialKeysNote              ← shown when SOME keys already present
│       └── "OPENROUTER_API_KEY already configured ✓"
│
├── ModalFooter
│   ├── SecondaryAction ("Cancel")
│   └── PrimaryAction                ← label changes by state (see §5)
│
└── ProgressOverlay                  ← shown during SAVING_KEYS and PROVISIONING
    ├── ProgressAnimation
    ├── ProgressLabel                ← "Saving keys…" / "Starting agent…"
    └── ProgressSteps (StepList)     ← see §4.3
```

---

## 4. Wireframe Layouts

### 4.1 State: MISSING_KEYS_MODAL — Initial View

```
┌────────────────────────────────────────────────────────┐
│  🤖  Set up required API keys              [×]         │
│  GitHub PR Reviewer                                    │
│  Automatically reviews pull requests with AI          │
├────────────────────────────────────────────────────────┤
│                                                        │
│  This template needs 2 API keys to run:               │
│                                                        │
│  ○  🐙  GITHUB_TOKEN                                  │
│         Read pull requests and post review comments    │
│                                                        │
│  ○  ◆   ANTHROPIC_API_KEY                            │
│         Run the LLM that analyzes code                 │
│                                                        │
├────────────────────────────────────────────────────────┤
│  GitHub Personal Access Token                         │
│  GITHUB_TOKEN                                          │
│  ┌──────────────────────────────────────────┐ [👁]   │
│  │ ••••••••••••••••••••••••••••••••••••••  │        │
│  └──────────────────────────────────────────┘        │
│  Expected: ghp_ or github_pat_ prefix                 │
│  Get a GitHub token →                                  │
│                                                        │
│  Anthropic API Key                                    │
│  ANTHROPIC_API_KEY                                     │
│  ┌──────────────────────────────────────────┐ [👁]   │
│  │ ••••••••••••••••••••••••••••••••••••••  │        │
│  └──────────────────────────────────────────┘        │
│  Expected: sk-ant- prefix                             │
│  Get an Anthropic key →                               │
│                                                        │
│  ▸ Also add optional keys (1)                         │
│                                                        │
├────────────────────────────────────────────────────────┤
│  [ Cancel ]                  [ Save & Deploy ]        │
└────────────────────────────────────────────────────────┘
```

### 4.2 State: MISSING_KEYS_MODAL — Partial Fill with Validation

```
┌────────────────────────────────────────────────────────┐
│  🤖  Set up required API keys              [×]         │
│  GitHub PR Reviewer                                    │
├────────────────────────────────────────────────────────┤
│                                                        │
│  ✓  🐙  GITHUB_TOKEN          ← filled + valid format │
│  ○  ◆   ANTHROPIC_API_KEY     ← still empty           │
│                                                        │
│  GitHub Personal Access Token                         │
│  GITHUB_TOKEN                                          │
│  ┌──────────────────────────────────────────┐ [👁]   │
│  │ ••••••••••••••••••••••••••••••••••••••  │        │
│  └──────────────────────────────────────────┘        │
│  ✓ Valid format                                       │
│                                                        │
│  Anthropic API Key                                    │
│  ANTHROPIC_API_KEY                                     │
│  ┌──────────────────────────────────────────┐ [👁]   │
│  │ sk-prod-abcd (still typing...)          │        │
│  └──────────────────────────────────────────┘        │
│  ⚠ Expected format: sk-ant-...                        │
│                                                        │
├────────────────────────────────────────────────────────┤
│  [ Cancel ]              [ Save & Deploy (1/2) ]      │
└────────────────────────────────────────────────────────┘
```

Note: Primary button shows `"Save & Deploy (1/2)"` while partial — disabled until all
required fields pass validation. Counter updates live.

### 4.3 State: PROVISIONING — Progress Steps

```
┌────────────────────────────────────────────────────────┐
│  🤖  Deploying GitHub PR Reviewer          [×]         │
│                                                        │
│  ━━━━━━━━━━━━━━━━━━━━━━━━░░░░░░░░░░░░░░░░  60%        │
│                                                        │
│  ✓  Keys saved                                        │
│  ✓  Workspace created                                 │
│  ⟳  Starting container...                ← animated   │
│  ○  Registering agent                                 │
│  ○  Ready                                             │
│                                                        │
│  This usually takes 15–30 seconds.                    │
│                                                        │
│  ────────────────────────────────────────────         │
│  [ Cancel deployment ]                                │
└────────────────────────────────────────────────────────┘
```

- Progress bar is real (tied to step completion events from server-sent events or polling)
- Steps are determined from heartbeat / webhook events, not a fake timer
- "Cancel deployment" is available throughout; triggers graceful teardown

### 4.4 State: PROVISION_TIMEOUT (replaces infinite spinner)

```
┌────────────────────────────────────────────────────────┐
│  🤖  Deployment taking longer than expected [×]        │
│                                                        │
│  ✓  Keys saved                                        │
│  ✓  Workspace created                                 │
│  ✗  Starting container — timed out                    │
│                                                        │
│  The agent didn't start within 30 seconds.            │
│  This is usually a temporary issue.                   │
│                                                        │
│  [ Try again ]              [ View logs ]             │
│                                                        │
│  Still having trouble? Contact support →              │
└────────────────────────────────────────────────────────┘
```

### 4.5 State: RUNTIME SECRET ERROR (key present but invalid at runtime)

```
┌────────────────────────────────────────────────────────┐
│  ⚠  Agent started but couldn't authenticate [×]       │
│  GitHub PR Reviewer                                    │
├────────────────────────────────────────────────────────┤
│                                                        │
│  The agent reported an authentication error           │
│  immediately after starting:                          │
│                                                        │
│  ┌──────────────────────────────────────────────────┐ │
│  │ GITHUB_TOKEN: 401 Unauthorized — token may be   │ │
│  │ expired or lack required scopes (repo, pr)      │ │
│  └──────────────────────────────────────────────────┘ │
│                                                        │
│  Update your key and the agent will restart:          │
│                                                        │
│  GITHUB_TOKEN                                          │
│  ┌──────────────────────────────────────────┐ [👁]   │
│  │ ••••••••••••••••••••••••••••••••••••••  │        │
│  └──────────────────────────────────────────┘        │
│  Enter new value to replace — current not shown       │
│  Get a new GitHub token →                             │
│                                                        │
├────────────────────────────────────────────────────────┤
│  [ Skip for now ]             [ Update & Restart ]    │
└────────────────────────────────────────────────────────┘
```

### 4.6 State: DEPLOY CANCELLED — Template Card Warning

```
┌──────────────────────────────────────────────────┐
│  GitHub PR Reviewer                              │
│  [template card content...]                      │
│                                                  │
│  ┌──────────────────────────────────────────┐   │
│  │  ⚠ Deployment cancelled                 │   │
│  │  Missing: GITHUB_TOKEN, ANTHROPIC_API_KEY│   │
│  │  [Add keys in Settings]  [Try again]  [×]│   │
│  └──────────────────────────────────────────┘   │
│                                                  │
│                        [ Deploy ]               │
└──────────────────────────────────────────────────┘
```

### 4.7 State: PROVISION_ERROR — Server Error (non-secret)

```
┌────────────────────────────────────────────────────────┐
│  ✗  Deployment failed                      [×]         │
│  GitHub PR Reviewer                                    │
├────────────────────────────────────────────────────────┤
│                                                        │
│  ✓  Keys saved                                        │
│  ✓  Workspace created                                 │
│  ✗  Container failed to start                         │
│                                                        │
│  Error: Out of capacity in us-east-1.                 │
│  Error code: WORKSPACE_CAPACITY_EXCEEDED              │
│                                                        │
│  [ Try again ]         [ Contact support ]            │
│                                                        │
│  Or try a different region in Settings →              │
└────────────────────────────────────────────────────────┘
```

---

## 5. Copy / Microcopy by State

### 5.1 CHECKING_SECRETS
- No UI change — instantaneous. If takes > 500ms (degraded API): show inline spinner on Deploy button only, no full modal.

### 5.2 MISSING_KEYS_MODAL

| Element | Copy |
|---|---|
| Modal title (all missing) | "Set up required API keys" |
| Modal title (some missing) | "Add 1 more API key" / "Add 2 more API keys" |
| Modal subtitle | "[Template name] needs these keys to run:" |
| Section intro | "This template needs [N] API key[s] to run:" |
| Purpose hint | From manifest `purpose` field — e.g. "Read pull requests and post review comments" |
| Field label | Service name + key type — "GitHub Personal Access Token" |
| Field hint (format) | "Expected: ghp_ or github_pat_ prefix" |
| Get key link | "Get a GitHub token →" / "Get an Anthropic key →" / "Get an OpenRouter key →" |
| Partial progress button | "Save & Deploy (1/2)" → "(2/2)" |
| All valid button | "Save & Deploy" |
| Cancel | "Cancel" |
| Optional keys toggle | "Also add optional keys (N)" |
| Already-present key note | "[KEY_NAME] is already configured ✓" |

### 5.3 SAVING_KEYS
| Element | Copy |
|---|---|
| Overlay label | "Saving keys…" |
| Step line | "Saving GITHUB_TOKEN…" → "✓ GITHUB_TOKEN saved" |

### 5.4 PROVISIONING
| Element | Copy |
|---|---|
| Modal title | "Deploying [Template Name]" |
| Step: keys saved | "Keys saved" |
| Step: workspace created | "Workspace created" |
| Step: container starting | "Starting container…" |
| Step: registering | "Registering agent" |
| Step: ready | "Ready" |
| Footer hint | "This usually takes 15–30 seconds." |
| Cancel | "Cancel deployment" |

### 5.5 PROVISION_TIMEOUT
| Element | Copy |
|---|---|
| Modal title | "Deployment taking longer than expected" |
| Body | "The agent didn't start within 30 seconds. This is usually a temporary issue." |
| Primary | "Try again" |
| Secondary | "View logs" |
| Footer | "Still having trouble? Contact support →" |

### 5.6 RUNTIME_SECRET_ERROR
| Element | Copy |
|---|---|
| Modal title | "Agent started but couldn't authenticate" |
| Body | "The agent reported an authentication error immediately after starting:" |
| Error box | "[KEY_NAME]: [error from agent verbatim, trimmed to 120 chars]" |
| Section intro | "Update your key and the agent will restart:" |
| Field hint | "Enter new value to replace — current not shown" |
| Get key link | "Get a new [service] [key type] →" |
| Primary | "Update & Restart" |
| Secondary | "Skip for now" |

### 5.7 PROVISION_ERROR (non-secret)
| Element | Copy |
|---|---|
| Modal title | "Deployment failed" |
| Body | "Error: [server message]. Error code: [code]" |
| Primary | "Try again" |
| Secondary | "Contact support" |
| Footer (if region relevant) | "Or try a different region in Settings →" |

### 5.8 DEPLOY_CANCELLED (template card warning)
| Element | Copy |
|---|---|
| Warning title | "Deployment cancelled" |
| Warning body | "Missing: [KEY_NAME], [KEY_NAME]" |
| Primary link | "Add keys in Settings" |
| Secondary link | "Try again" |

### 5.9 Validation hint copy (inline, per service)

| State | Copy |
|---|---|
| Not yet typed | *(no hint shown)* |
| Invalid format | "⚠ Expected format: [prefix]..." |
| Valid format | "✓ Valid format" |
| Test connection: loading | "Testing…" |
| Test connection: success | "Connected ✓" |
| Test connection: 401 | "Invalid key — permission denied." |
| Test connection: 403 | "Key valid but missing required scopes. [See docs →]" |
| Test connection: timeout | "Connection timed out. Service may be down." |
| Save error: network | "Failed to save. Check your connection and try again. [Retry]" |
| Save error: conflict | "A key named [X] already exists. [Edit in Settings →]" |

---

## 6. Edge Cases

### 6.1 Only Some Keys Are Missing

- Modal shows **only the missing keys** in the entry form
- Already-present keys shown as read-only confirmation rows with ✓:
  ```
  ✓  OPENROUTER_API_KEY  ·  already configured
  ```
- Copy adjusts: "Add 1 more API key" not "Set up required API keys"
- Primary button shows "Save & Deploy" (not "Save 3 keys & Deploy")

### 6.2 Key Passes Format Validation But Fails at Runtime

This is the "silent failure" case — key looks valid (correct prefix, correct length) but
is expired, revoked, or lacks required scopes.

**Detection point:** Agent starts, immediately calls the external service, gets 401/403,
reports error via activity log or heartbeat `last_sample_error`.

**Detection mechanism:**
- After `AGENT_RUNNING` state is reached, platform listens for `runtime_auth_error` event
  for 10 seconds (grace period for agent initialization)
- If event received → transition to `RUNTIME_SECRET_ERROR` state
- Modal re-opens over the now-running-but-broken agent card

**Recovery:**
- User updates key in the Runtime Secret Error modal
- On save: platform sets new env var and sends `RESTART` signal to container
- Container restarts (not re-provisioned — faster, ~5s)
- Re-enter `PROVISIONING` flow at the "Starting container" step

### 6.3 User Has No Internet Mid-Flow

| Stage when offline | Behavior |
|---|---|
| During `CHECKING_SECRETS` | Deploy button shows spinner for 5s, then: "Couldn't check your keys. Check your connection." Banner on canvas, modal doesn't open |
| During `SAVING_KEYS` | Save fails with inline error per key; retry available; modal stays open |
| During `PROVISIONING` | Heartbeat stops; after 10s: "Lost connection during deployment. [Check status]" |

### 6.4 User Adds Keys Then Immediately Closes Browser

- Keys are saved server-side as soon as each one is individually confirmed (not batched on modal close)
- If browser closes during `PROVISIONING`: deployment continues server-side
- On next page load: if agent is running → show normally; if failed → show error card on canvas

### 6.5 Template Requires a Key the Platform Doesn't Support

- If `service` in manifest doesn't map to a known service (no logo, no format validation):
  - Falls back to `Custom` service display
  - No format validation (accept any non-empty value)
  - No "Get a key" link
  - No test connection button

### 6.6 Duplicate Key Name Already Exists with Different Value

Server returns 409 on save attempt:
```
⚠ GITHUB_TOKEN already exists with a different value.
  Saving this will overwrite the existing key.
  [ Keep existing ]    [ Overwrite ]
```
- "Keep existing" → skips that key, continues with others, deploys using existing value
- "Overwrite" → saves new value, continues to deploy

### 6.7 Rate Limiting / Too Many Keys Saved

Server returns 429:
```
⚠ Too many changes at once. Please wait a moment and try again.
```
Retry with 5s automatic backoff; shown as progress indicator not error.

### 6.8 Deployment Retry Limit

After 2 automatic retries post `PROVISION_TIMEOUT`, stop auto-retrying:
```
✗ Deployment failed after 2 attempts.
  This may be a temporary platform issue.
  [ Try manually later ]    [ Contact support ]
```

### 6.9 User Navigates Away During Modal

If user clicks canvas background (outside modal) while `MISSING_KEYS_MODAL` is open:
- Modal does NOT close (it's task-critical, not dismissible by backdrop click — unlike Settings Panel)
- The backdrop is non-interactive
- Only explicit Cancel or × triggers the cancel guard

### 6.10 Multiple Templates Deploying Simultaneously

Each template deployment opens its own interception modal instance. If two modals would
stack, queue them: second modal opens after first is dismissed (success or cancel).
Show a queue indicator: "1 more deployment waiting."

---

## 7. Progress Steps Specification

Steps are event-driven (not time-based). Each step corresponds to a server event:

| Step | Trigger Event | Timeout |
|---|---|---|
| "Keys saved" | POST `/secrets` returns 200 for all keys | 3s per key |
| "Workspace created" | POST `/workspaces` returns 201 | 5s |
| "Starting container..." | `workspace.status = provisioning` heartbeat | 15s |
| "Registering agent" | `workspace.status = starting` heartbeat | 10s |
| "Ready" | `workspace.status = online` heartbeat | 10s |

If any step times out: that step shows `✗` and the `PROVISION_TIMEOUT` state is entered.

Total max duration: 3 + 5 + 15 + 10 + 10 = **43s** (in practice much faster). The
"30 seconds" shown to user is the UX expectation, not a hard kill timeout; the system
waits the full per-step timeout.

---

## 8. Integration with Settings Panel Spec

### 8.1 Shared Components

The following components from `ux-spec-settings-panel.md` are reused verbatim in this
interception flow. Do not create parallel implementations:

| Component | Settings Panel Location | Reused In |
|---|---|---|
| `KeyValueField` (password input + reveal toggle) | `AddKeyForm > KeyValueField` | `KeyEntryField > ValueInput` |
| `ValidationHint` (format feedback) | `AddKeyForm > ValidationHint` | `KeyEntryField > ValidationHint` |
| `TestConnectionButton` + all its states | `AddKeyForm > TestConnectionButton` | `KeyEntryField > TestConnectionButton` |
| `RevealToggle` (eye icon) | `SecretRow > RevealToggle` | `KeyEntryField > RevealToggle` |
| Key masking rules (§5 of Settings Panel spec) | Applies to SecretRow display | `KeyEntryField` masked display |
| Unsaved changes guard dialog | Panel-level | Modal-level cancel guard (§2.2) |
| Validation rules by service (§6 of Settings Panel spec) | Format regex table | Identical regexes applied here |
| Delete confirmation dialog | `DeleteConfirmDialog` | Not reused (no deletion in this flow) |

### 8.2 "Add Keys in Settings" Deep Link

When user cancels a deployment (§2.2 cancel path), the "Add keys in Settings" link on
the template card warning must:
1. Open the Settings Panel (gear icon activation)
2. Deep-link to the "API Keys" tab
3. Pre-scroll to the first missing key's service group
4. Auto-expand the `AddKeyForm` with the service pre-selected

This requires a URL-hash or programmatic Settings Panel API:
```
openSettingsPanel({ tab: 'api-keys', highlightService: 'github', expandAddForm: true })
```

### 8.3 "Test Connection" Shares Validation Infrastructure

Both the Settings Panel and this modal call the same underlying test-connection endpoint:
```
POST /platform/secrets/test
{ service: "github", value: "ghp_..." }
→ { status: "valid" | "invalid", error?: string, scopes?: string[] }
```

This is the single source of truth for connection validation — the modal does not have a
separate validation path.

### 8.4 Keys Saved Here Appear Immediately in Settings Panel

If user opens the Settings Panel after a successful modal flow, the newly saved keys must
appear in the grouped list immediately (optimistic UI + server confirmation). No page
refresh required. The Settings Panel should subscribe to a secrets-updated event or
invalidate its cache on panel open.

---

## 9. Accessibility

### 9.1 Modal Behavior
- `role="dialog"` with `aria-modal="true"` (unlike Settings Panel which is `aria-modal="false"`)
- Focus **trapped** within modal (Tab cycles through modal elements only)
- `aria-labelledby` pointing to ModalTitle
- `aria-describedby` pointing to ModalSubtitle

### 9.2 Progress Announcements
```html
<div aria-live="assertive" aria-atomic="true">
  <!-- updated as each step completes -->
  "Step 3 of 5: Starting container..."
  "Step 4 of 5: Registering agent"
  "Deployment complete. GitHub PR Reviewer is now running."
</div>
```
Use `aria-live="assertive"` (not polite) so screen reader users hear progress without waiting.

### 9.3 Error Announcements
- Validation errors: `aria-live="polite"` on `ValidationHint` element; announced on change
- Timeout/failure: `aria-live="assertive"` — high priority interrupt

### 9.4 Keyboard Navigation
| Key | Action |
|---|---|
| `Tab` / `Shift+Tab` | Cycle through fields and buttons |
| `Escape` | Triggers cancel guard (does NOT immediately close) |
| `Enter` | Submits form when primary button is focused |
| `Space` | Toggles reveal/hide on focused RevealToggle |

### 9.5 Focus Management
- Modal opens → focus on first empty key field (or primary button if all fields pre-filled)
- Validation error → focus moves to the first invalid field
- Progress overlay shown → focus moves to the ProgressLabel heading
- Error state → focus moves to the error heading
- Modal closes (success) → focus moves to the deployed agent card on the canvas

---

## 10. Responsive Behavior

| Viewport | Modal Behavior |
|---|---|
| Desktop (≥1024px) | 560px centered modal, backdrop covers canvas |
| Tablet (768–1023px) | 90vw modal, scrollable body |
| Mobile (<768px) | Full-screen bottom sheet; steps shown as condensed list |

---

*End of Onboarding Interception Flow UX Spec v1.0*
