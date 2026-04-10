# UX Spec: Deploy Interception Flow — Secret Pre-check
**Version:** 1.0  
**Date:** 2026-04-09  
**Author:** UI/UX Designer Agent  
**Status:** Ready for Engineering Review

---

## 0. Problem Statement

When a user deploys a LangGraph agent from a template, the system currently provisions the workspace immediately. If required secrets are missing, the workspace starts but fails silently — the user sees an infinite "Starting…" spinner with no actionable feedback and no way to recover without knowing to navigate to Settings.

**Goal:** Intercept the deploy flow *before* provisioning, check required secrets, and surface a clear inline resolution path if any are missing. If the user skips resolution, show a specific, actionable error state on the workspace card — never a hanging spinner.

---

## 1. Trigger and Preconditions

**Trigger:** User clicks **"Deploy"** (or "Use Template", "Create Workspace") on any workspace template card.

**Preconditions the system must evaluate before proceeding:**
1. Template metadata declares a `required_secrets` list (e.g., `[ANTHROPIC_API_KEY, GITHUB_TOKEN]`)
2. System queries the platform secrets store for the current user/org
3. Compares declared requirements against stored keys

**Three outcomes from this check:**

| Outcome | Condition | Path |
|---|---|---|
| **All present & valid** | Every required key exists and passes format check | Proceed directly to deploy |
| **Some missing** | ≥1 required key not found in secrets store | Show Missing Keys Modal |
| **Some invalid** | Key exists but fails format validation or last test-connection failed | Show Invalid Keys Modal (variant) |

---

## 2. Full State Machine

```
[User clicks Deploy]
         │
         ▼
[CHECKING_SECRETS]
  ├── spinner on Deploy button (300ms debounce before showing)
  ├── button label: "Checking…"
  └── button disabled
         │
         ├──────────────────────────────────────────────────────────────┐
         │ all secrets present & valid                                  │ secrets missing or invalid
         ▼                                                              ▼
[DEPLOY_PROCEEDING]                                          [INTERCEPTION_MODAL_OPEN]
  ├── modal closes (if any)                                    ├── modal appears (see §4)
  ├── workspace card enters PROVISIONING state                 ├── lists exactly which keys are missing
  └── progress indicator shown on card                        └── provides inline input fields
                                                                       │
                                                         ┌─────────────┼──────────────────┐
                                                         │             │                  │
                                              user fills keys    user clicks       user presses
                                              & clicks           "Cancel" or       Escape or
                                              "Set Keys          dismisses         closes modal
                                              & Deploy"          without filling              │
                                                         │             │                     │
                                                         ▼             ▼                     ▼
                                               [SAVING_SECRETS] [DEPLOY_CANCELLED]   [DEPLOY_CANCELLED]
                                                 ├── spinner          │                     │
                                                 ├── fields           └─────────────────────┘
                                                 │   disabled                   │
                                                 │                              ▼
                                                 │                    [CARD_ERROR_STATE]
                                                 │                      ├── card shows error banner
                                                 │                      ├── spinner replaced with ✗
                                                 │                      └── "Configure Keys" button
                                                 │
                                                 ├── save success
                                                 │       ▼
                                                 │   [RE_CHECKING_SECRETS]
                                                 │       │
                                                 │       ├── all present ──► [DEPLOY_PROCEEDING]
                                                 │       └── still missing ──► [INTERCEPTION_MODAL_OPEN]
                                                 │                             (with error inline)
                                                 │
                                                 └── save failure
                                                         ▼
                                                 [SAVE_ERROR]
                                                   ├── inline error in modal
                                                   └── fields re-enabled; user can retry
```

---

## 3. Component Hierarchy

```
DeployButton (entry point on template card)
│
└── DeployOrchestrator (state machine controller, no visual)
    ├── SecretsCheckIndicator (inline on Deploy button during check)
    │
    ├── MissingSecretsModal (shown when secrets missing/invalid)
    │   ├── ModalHeader
    │   │   ├── ModalTitle ("Almost ready to deploy")
    │   │   └── CloseButton (×)
    │   │
    │   ├── ModalBody
    │   │   ├── ContextBlock
    │   │   │   ├── TemplateIcon + TemplateLabel  ← "Deploying: Code Review Agent"
    │   │   │   └── ExplanationText
    │   │   │
    │   │   ├── MissingKeysList
    │   │   │   └── MissingKeyRow [repeats per missing key]
    │   │   │       ├── ServiceBadge         ← e.g. "Anthropic"
    │   │   │       ├── KeyNameLabel         ← "ANTHROPIC_API_KEY"
    │   │   │       ├── RequiredReasonText   ← "Used to run the LLM"
    │   │   │       ├── SecretValueInput     ← password field
    │   │   │       ├── RevealToggle         ← eye icon
    │   │   │       ├── ValidationHint       ← real-time format feedback
    │   │   │       └── TestConnectionButton ← optional, per supported service
    │   │   │
    │   │   └── InvalidKeysList (variant: key exists but is invalid)
    │   │       └── InvalidKeyRow [repeats]
    │   │           ├── KeyNameLabel + WarningBadge  ← "OPENROUTER_API_KEY  ⚠ Invalid"
    │   │           ├── SecretValueInput (pre-populated masked)
    │   │           └── ValidationHint
    │   │
    │   └── ModalFooter
    │       ├── SkipLink ("Deploy without these keys →")  ← secondary, understated
    │       ├── CancelButton
    │       └── SetAndDeployButton ("Set Keys & Deploy")
    │
    └── WorkspaceCard (target card being deployed)
        ├── CardHeader (name, template label)
        ├── CardStatusArea
        │   ├── ProvisioningIndicator  ← shown during DEPLOY_PROCEEDING
        │   ├── ErrorBanner            ← shown during CARD_ERROR_STATE
        │   │   ├── ErrorIcon (✗)
        │   │   ├── ErrorTitle ("Missing required API keys")
        │   │   ├── ErrorKeyList       ← bullet list of missing key names
        │   │   └── ConfigureKeysButton ("Configure Keys")
        │   └── RunningIndicator       ← shown when deployed successfully
        └── CardActions
```

---

## 4. MissingSecretsModal — Detailed Spec

### 4.1 Appearance Trigger

Modal appears **centered** over the canvas with backdrop overlay (`rgba(0,0,0,0.4)`).  
Animation: fade-in + scale-up from 95% → 100%, 180ms ease-out.  
Not a slide-over — this is a **blocking decision point**, so a centered modal is correct here (unlike the Settings panel which is a non-blocking tool).

### 4.2 Wireframe — Missing Keys (2 keys)

```
┌───────────────────────────────────────────────────────────────┐
│                                                               │
│  Almost ready to deploy                              [×]      │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  📦  Code Review Agent                                  │ │
│  │      Requires 2 API keys before deployment can start    │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                               │
│  ANTHROPIC_API_KEY                        Anthropic           │
│  Used to run the language model                               │
│  ┌──────────────────────────────────────────────────┐  [👁]  │
│  │                                                  │        │
│  └──────────────────────────────────────────────────┘        │
│  Enter your Anthropic API key (sk-ant-...)                    │
│                                                               │
│  GITHUB_TOKEN                             GitHub              │
│  Used to read and write pull requests                         │
│  ┌──────────────────────────────────────────────────┐  [👁]  │
│  │                                                  │        │
│  └──────────────────────────────────────────────────┘        │
│  Enter your GitHub personal access token (ghp_...)           │
│                                                               │
│                        Deploy without these keys →           │
│  [ Cancel ]                       [ Set Keys & Deploy ]      │
│                                                               │
└───────────────────────────────────────────────────────────────┘
```

### 4.3 Wireframe — Invalid Keys (1 invalid, 1 missing)

```
┌───────────────────────────────────────────────────────────────┐
│                                                               │
│  Action needed before deployment                     [×]      │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  📦  Code Review Agent                                  │ │
│  │      1 key is invalid · 1 key is missing                │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                               │
│  OPENROUTER_API_KEY                  ⚠ Invalid  OpenRouter   │
│  Current key failed validation — please update               │
│  ┌──────────────────────────────────────────────────┐  [👁]  │
│  │  ••••••••••••••••••••••••••••••••••••••••••••    │        │
│  └──────────────────────────────────────────────────┘        │
│  ⚠  Does not match expected format sk-or-...                 │
│                                                               │
│  ANTHROPIC_API_KEY                       Missing  Anthropic  │
│  Required to run the language model                          │
│  ┌──────────────────────────────────────────────────┐  [👁]  │
│  │                                                  │        │
│  └──────────────────────────────────────────────────┘        │
│                                                               │
│                        Deploy without these keys →           │
│  [ Cancel ]                       [ Fix Keys & Deploy ]      │
│                                                               │
└───────────────────────────────────────────────────────────────┘
```

### 4.4 "Set Keys & Deploy" Button Logic

The primary CTA button is **disabled** until:
- All missing key fields are non-empty AND
- All filled values pass format validation

Button label variants:
- 1 key to set: "Set Key & Deploy"
- 2+ keys to set: "Set Keys & Deploy"
- All keys are invalid (not missing): "Fix Keys & Deploy"
- Mix: "Set & Fix Keys — Deploy"

### 4.5 "Deploy without these keys" Skip Link

- Shown as a small, right-aligned text link — not a button — to discourage use
- Clicking triggers a **secondary confirmation tooltip** inline:

```
  Deploy without these keys →
  ┌─────────────────────────────────────┐
  │  Agent may not function correctly.  │
  │  [  Confirm skip  ]  [  Go back  ] │
  └─────────────────────────────────────┘
```

- "Confirm skip" proceeds to deploy, bypassing secret check
- After skip: workspace card shows yellow warning banner (not red error) — "Deployed without all required keys. Some features may not work. [Configure Keys]"

---

## 5. Deploy Button States

The Deploy button on the template card cycles through these states:

```
[DEFAULT]
  Label:     "Deploy"
  Style:     Primary CTA (blue/accent)
  Disabled:  false

[CHECKING]  ← secret pre-check in progress
  Label:     "Checking…"
  Style:     Primary, dimmed
  Disabled:  true
  Left icon: spinner (16px)
  Max duration: 3s — if check takes >3s, fall through to DEPLOY_PROCEEDING
                 with a background check (don't block the user forever)

[BLOCKED]   ← secrets missing, modal open
  Label:     "Deploy"
  Style:     Primary, normal (modal handles the UX)
  Disabled:  false (modal is open, button is behind backdrop)

[DEPLOYING] ← provisioning in progress
  Label:     "Deploying…"
  Style:     Primary, dimmed
  Disabled:  true
  Left icon: spinner

[DEPLOYED]  ← workspace online
  Label:     "Open"
  Style:     Secondary
  Disabled:  false
```

---

## 6. Workspace Card Error State

### 6.1 When it appears

User dismissed the MissingSecretsModal (Cancel, Escape, or backdrop click) without providing the required keys.

### 6.2 Wireframe — Card Error State

```
┌─────────────────────────────────────────────────────┐
│  Code Review Agent                   [⋯ Options]    │
│  LangGraph · claude-sonnet-4-6                      │
│                                                      │
│  ┌─────────────────────────────────────────────┐   │
│  │  ✗  Missing required API keys               │   │
│  │                                             │   │
│  │  • ANTHROPIC_API_KEY                        │   │
│  │  • GITHUB_TOKEN                             │   │
│  │                                             │   │
│  │  [ Configure Keys ]                         │   │
│  └─────────────────────────────────────────────┘   │
│                                                      │
│  [ Deploy ]                                         │
└─────────────────────────────────────────────────────┘
```

### 6.3 Error Banner Spec

| Property | Value |
|---|---|
| Background | `#FEF2F2` (red-50) |
| Border | `1px solid #FCA5A5` (red-300), radius 6px |
| Icon | `✗` in `#DC2626` (red-600), 16px |
| Title text | "Missing required API keys" — 14px semibold, `#991B1B` |
| Key list | Bulleted, 13px regular, `#7F1D1D` |
| Button | "Configure Keys" — small secondary button, opens MissingSecretsModal |

### 6.4 Card States Summary

| State | Visual | Spinner? | Actionable? |
|---|---|---|---|
| Ready to deploy | Normal card | — | Deploy button |
| Checking secrets | Deploy button shows "Checking…" | Yes (on button only) | No |
| Modal open (missing keys) | Card + modal overlay | No | In modal |
| Deploying | Card with progress bar | Yes (on card) | Cancel button |
| Error: missing keys | Red banner on card | **No** | "Configure Keys" button |
| Error: deploy failed | Red banner (different copy) | **No** | "Retry" button |
| Warning: skipped keys | Yellow banner on card | No | "Configure Keys" link |
| Deployed / Running | Green status indicator | No | "Open" / "View Logs" |

The key design principle: **no state should show an indeterminate spinner without a defined timeout and fallback**. If the secret check times out (>3s), proceed optimistically and handle any resulting deploy error at the provisioning layer.

---

## 7. Interaction Flows — Detailed Walkthroughs

### 7.1 Happy Path (All Keys Present)

1. User clicks "Deploy" on template card
2. Button transitions to "Checking…" with spinner
3. System checks secrets store: all required keys found and format-valid
4. Button transitions to "Deploying…"
5. Workspace card enters provisioning state with progress indicator
6. On success: card shows "Running" status, button becomes "Open"

*Total added latency: 1 API call (~100–300ms). Imperceptible to user.*

### 7.2 Missing Keys Path (Resolution in Modal)

1. User clicks "Deploy"
2. Button: "Checking…"
3. Check returns: ANTHROPIC_API_KEY missing
4. Modal opens with 1 key field
5. User types API key value
6. Real-time validation: format check passes → hint turns green
7. User clicks "Set Key & Deploy"
8. Modal footer: button shows spinner "Saving…", all inputs disabled
9. Secret saved to platform store
10. Modal re-checks secrets → all present
11. Modal closes with fade-out (180ms)
12. Card enters provisioning state
13. Toast: "API key saved · Deployment started"

### 7.3 Missing Keys Path (User Cancels)

1. Steps 1–4 same as above
2. User clicks "Cancel" or presses Escape
3. Modal closes
4. Workspace card shows red error banner:
   - "Missing required API keys: ANTHROPIC_API_KEY"
   - "Configure Keys" button
5. "Deploy" button re-enabled on the card
6. User can either:
   - a. Click "Configure Keys" → modal reopens in same state
   - b. Click "Deploy" → re-triggers the whole check flow
   - c. Navigate to Settings (⚙) → add key there → return to card → click Deploy

### 7.4 Invalid Key Path

1. User clicks "Deploy"
2. Check returns: OPENROUTER_API_KEY exists but fails format validation
3. Modal opens showing the key as "⚠ Invalid" with the existing masked value
4. User must clear and retype the correct value (cannot save same invalid value)
5. On valid input: "Fix Keys & Deploy" button enables
6. Flow continues as 7.2 from step 7 onward

### 7.5 Save Fails in Modal

1. User fills keys, clicks "Set Keys & Deploy"
2. Save request fails (network error or 4xx)
3. Modal shows inline error banner at top of modal body:
   ```
   ┌─────────────────────────────────────────┐
   │  ⚠  Failed to save keys. Try again.    │
   └─────────────────────────────────────────┘
   ```
4. Inputs re-enabled, button re-enabled
5. User can retry; no deployment is started

---

## 8. Template Metadata — Required Secrets Declaration

For the pre-check to work, templates must declare their secret requirements. Proposed schema:

```yaml
# template.yaml
name: "Code Review Agent"
runtime: langgraph
required_secrets:
  - key: ANTHROPIC_API_KEY
    service: anthropic
    reason: "Used to run the language model"
    required: true
  - key: GITHUB_TOKEN
    service: github
    reason: "Used to read and write pull requests"
    required: true
  - key: OPENROUTER_API_KEY
    service: openrouter
    reason: "Fallback model provider"
    required: false   ← optional: shown in modal but does not block deploy
```

`required: false` keys are shown in the modal with a "(Optional)" badge and do not block the "Set Keys & Deploy" CTA. They are not listed in the card error state.

---

## 9. Validation Rules (same as Settings Panel spec)

| Service | Expected Format | Hint Text |
|---|---|---|
| Anthropic | `sk-ant-` prefix, 90+ chars | "Enter your Anthropic API key (sk-ant-...)" |
| GitHub | `ghp_` or `github_pat_` prefix | "Enter a GitHub personal access token (ghp_...)" |
| OpenRouter | `sk-or-` prefix | "Enter your OpenRouter API key (sk-or-...)" |
| Custom | Non-empty | "Enter the value for this secret" |

Validation fires **400ms after user stops typing** (debounced). Always validates on blur.

---

## 10. Accessibility Specification

### 10.1 Modal Focus Management

- On open: focus moves to first empty SecretValueInput (or first input if all empty)
- Tab order: inputs in declaration order → "Deploy without keys" link → Cancel → Set & Deploy
- Escape: closes modal → returns focus to Deploy button on template card
- Modal has `role="dialog"`, `aria-modal="true"`, `aria-labelledby` pointing to title

### 10.2 ARIA Markup

```html
<div
  role="dialog"
  aria-modal="true"
  aria-labelledby="modal-title"
  aria-describedby="modal-desc"
>
  <h2 id="modal-title">Almost ready to deploy</h2>
  <p id="modal-desc">
    The following API keys are required before Code Review Agent can be deployed.
  </p>

  <!-- Per missing key -->
  <div role="group" aria-label="ANTHROPIC_API_KEY — required">
    <label for="input-anthropic">ANTHROPIC_API_KEY</label>
    <input
      id="input-anthropic"
      type="password"
      autocomplete="off"
      aria-required="true"
      aria-describedby="hint-anthropic"
    />
    <p id="hint-anthropic" role="status">Enter your Anthropic API key (sk-ant-...)</p>
  </div>

  <!-- CTA -->
  <button aria-disabled="true" aria-describedby="cta-hint">
    Set Keys &amp; Deploy
  </button>
  <p id="cta-hint">Fill in all required keys above to enable deployment</p>
</div>
```

### 10.3 Card Error State Accessibility

```html
<div role="alert" aria-live="assertive">
  <p>Missing required API keys: ANTHROPIC_API_KEY, GITHUB_TOKEN.</p>
  <button aria-label="Configure missing API keys for Code Review Agent">
    Configure Keys
  </button>
</div>
```

Using `role="alert"` ensures screen readers announce the error immediately when the card enters the error state (after modal dismiss).

### 10.4 Keyboard-Only Flow

- Full flow completable via keyboard: Tab to Deploy → Enter → Tab to first input → type key → Tab to Set & Deploy → Enter
- No mouse required at any point

---

## 11. Edge Cases

| Scenario | Behavior |
|---|---|
| Template has no `required_secrets` declared | Skip pre-check entirely; proceed directly to deploy |
| Secrets store API is unreachable during check | Skip pre-check (optimistic path); if deploy fails, error is handled at provisioning layer; log warning |
| User has correct key in Settings but template declares a different name | Pre-check uses exact name match; if names differ, counts as missing — engineer must ensure template `key` names align with secrets store keys |
| User sets keys in modal then navigates away before clicking CTA | Secrets are saved (if they clicked "Test" which triggers an auto-save); if not saved, keys are lost — do NOT auto-save on typing, only on explicit action |
| User opens two deploy modals simultaneously | Prevent: Deploy button disabled while any deploy modal is open |
| All required keys are optional (required: false) | No modal shown; proceed directly to deploy; optional warning toast "2 optional keys are not configured" |
| Key saved in modal but deploy provisioning fails (infra error) | Show standard deploy error on card ("Deploy failed. Retry?") — keys remain saved in secrets store |
| Modal open + user opens Settings panel | Settings panel opens behind modal; modal stays on top; user can set keys in Settings, then close Settings, and the modal's "Set Keys & Deploy" flow will re-verify |

---

## 12. Integration Points for Engineering

| Concern | Implementation Note |
|---|---|
| Secret pre-check API | `GET /api/secrets/check?keys=ANTHROPIC_API_KEY,GITHUB_TOKEN` returns `{ present: [...], missing: [...], invalid: [...] }` |
| Save secrets from modal | `POST /api/secrets` (same endpoint as Settings panel) — reuse existing secrets store |
| Template metadata | Parse `required_secrets` from `template.yaml` at deploy-click time; cache per template |
| Card error state persistence | Store error state in workspace card local state; clear on successful deploy |
| Timeout for secret check | Abort after 3000ms, proceed optimistically to avoid blocking deploy on slow API |

---

*End of Deploy Interception Flow UX Spec v1.0*
