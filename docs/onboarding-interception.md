# Phase 20.2: Onboarding / Deploy Interception

## Overview

This feature adds three safety mechanisms around the workspace deployment flow:

1. **Pre-deploy secret check per runtime** — validates required API keys before deploying
2. **Missing Keys Modal** — inline key entry UI when secrets are missing
3. **Provisioning timeout with recovery** — timeout detection with Retry/Cancel/View Logs actions

## Architecture

```
User clicks Deploy
       │
       ▼
┌──────────────────┐
│ checkDeploySecrets│  ← deploy-preflight.ts
│  (per runtime)    │
└────────┬─────────┘
         │
    ┌────┴────┐
    │ OK?     │
    ├─ Yes ──→ POST /workspaces (deploy)
    │         │
    └─ No  ──→ MissingKeysModal
              │  ├─ Add keys inline → PUT /settings/secrets
              │  ├─ Open Settings Panel
              │  └─ Cancel Deploy
              │
              ▼ (after keys added)
         POST /workspaces (deploy)
              │
              ▼
    ┌──────────────────┐
    │ Provisioning...  │  ← ProvisioningTimeout watches
    │ (status tracking)│     nodes with status="provisioning"
    └────────┬─────────┘
             │
      ┌──────┴───────┐
      │ Timeout?     │  (default: 120s)
      ├─ No → Online │
      └─ Yes ─→ Timeout Banner
                 ├─ Retry  → POST /restart
                 ├─ Cancel → DELETE /workspaces/:id
                 └─ View Logs → Open Terminal tab
```

## Components

### `deploy-preflight.ts` — Pre-deploy Secret Validation

**Path:** `canvas/src/lib/deploy-preflight.ts`

Pure utility module with no side effects (except the API-calling `checkDeploySecrets`).

#### Required Keys Per Runtime

| Runtime | Required Keys |
|---------|--------------|
| langgraph | `OPENAI_API_KEY` |
| claude-code | `ANTHROPIC_API_KEY` |
| openclaw | `OPENAI_API_KEY` |
| deepagents | `OPENAI_API_KEY` |
| crewai | `OPENAI_API_KEY` |
| autogen | `OPENAI_API_KEY` |

These are derived from `workspace-configs-templates/*/config.yaml` → `env.required` fields.

#### Exports

```typescript
// Pure helpers (easily testable, no side effects)
getRequiredKeys(runtime: string): string[]
findMissingKeys(runtime: string, configuredKeys: Set<string>): string[]
getKeyLabel(key: string): string

// API-calling check
checkDeploySecrets(runtime: string, workspaceId?: string): Promise<PreflightResult>
```

### `MissingKeysModal.tsx` — Missing Keys Dialog

**Path:** `canvas/src/components/MissingKeysModal.tsx`

Modal dialog that appears when pre-deploy check finds missing API keys.

#### Props

| Prop | Type | Description |
|------|------|-------------|
| `open` | `boolean` | Whether to show the modal |
| `missingKeys` | `string[]` | Keys that need to be configured |
| `runtime` | `string` | Target runtime name |
| `onKeysAdded` | `() => void` | Called when all keys saved + user clicks Deploy |
| `onCancel` | `() => void` | Called on cancel / escape |
| `onOpenSettings` | `() => void` | Optional — opens Settings Panel |
| `workspaceId` | `string` | Optional — saves secrets at workspace scope |

#### Features

- Lists each missing key with a human-readable label
- Inline password input with Save button per key
- Visual confirmation when each key is saved (green checkmark)
- "Deploy" button only activates when all keys are saved
- "Cancel Deploy" button to abort
- Optional "Open Settings Panel" link for advanced configuration
- Keyboard: Escape to cancel, Enter to save current key
- Follows existing modal patterns (backdrop, dark theme, `z-50`)

### `ProvisioningTimeout.tsx` — Timeout Detection & Recovery

**Path:** `canvas/src/components/ProvisioningTimeout.tsx`

Fixed-position banner component rendered in the Canvas. Monitors nodes with `status === "provisioning"` and surfaces a timeout warning after a configurable threshold.

#### Props

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `timeoutMs` | `number` | `120000` (2 min) | Timeout threshold in milliseconds |

#### Recovery Actions

| Action | API Call | Effect |
|--------|----------|--------|
| **Retry** | `POST /workspaces/:id/restart` | Re-provisions the workspace |
| **Cancel** | `DELETE /workspaces/:id` | Removes the workspace |
| **View Logs** | — | Opens Terminal tab in SidePanel |

#### Behavior

- Starts tracking when a node enters `provisioning` status
- Checks every 5 seconds if any tracked node has exceeded the timeout
- Removes tracking when node transitions to `online`, `failed`, or is deleted
- Multiple timeouts can display simultaneously (stacked banners)
- Shows elapsed time in human-readable format (e.g., "2m 30s")

### `WORKSPACE_PROVISION_FAILED` Event

Added handler in `canvas-events.ts` for the existing platform event. When provisioning fails:
- Sets node status to `"failed"`
- Stores error message in `lastSampleError`
- Displays error in the WorkspaceNode component (existing failed state rendering)

## Integration Points

### TemplatePalette

The "Deploy" button in TemplatePalette now runs `checkDeploySecrets()` before calling the workspace creation API. If missing keys are found, the `MissingKeysModal` is shown. After keys are added, deploy proceeds automatically.

### Canvas

`ProvisioningTimeout` is rendered inside the Canvas component alongside other overlays (Toaster, ApprovalBanner, etc.).

## Testing

### Unit Tests

- **`deploy-preflight.test.ts`** — Tests all pure functions (`getRequiredKeys`, `findMissingKeys`, `getKeyLabel`) and the API-calling `checkDeploySecrets` with mocked fetch (success, failure, workspace-scoped)
- **`MissingKeysModal.test.tsx`** — Tests component interface, render/no-render behavior, prop handling
- **`ProvisioningTimeout.test.tsx`** — Tests store integration (provisioning node detection, state transitions via events, restart/remove/select actions, multi-node scenarios)

### Running Tests

```bash
cd canvas && npm test
```

## Configuration

The provisioning timeout threshold can be configured by passing `timeoutMs` to the `ProvisioningTimeout` component. To change the default:

```tsx
<ProvisioningTimeout timeoutMs={180_000} />  {/* 3 minutes */}
```

To add new runtime key requirements, update `RUNTIME_REQUIRED_KEYS` in `deploy-preflight.ts`.
