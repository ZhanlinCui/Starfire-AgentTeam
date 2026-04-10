import type { Secret } from '@/types/secrets';

/**
 * Secrets CRUD API client.
 *
 * NOTE: These endpoints do not exist on the platform yet (confirmed by
 * Backend Engineer 2026-04-09). During development, back with MSW mock
 * handlers. The contracts below are the agreed-upon target shape.
 */

const PLATFORM_URL = process.env.NEXT_PUBLIC_PLATFORM_URL ?? 'http://localhost:8080';

function apiUrl(workspaceId: string, path = ''): string {
  // "global" workspaceId → use /settings/secrets (global secrets)
  // Otherwise → use /workspaces/:id/secrets (workspace secrets)
  if (workspaceId === 'global') {
    return `${PLATFORM_URL}/settings/secrets${path}`;
  }
  return `${PLATFORM_URL}/workspaces/${workspaceId}/secrets${path}`;
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...init?.headers,
    },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ message: res.statusText }));
    throw new ApiError(res.status, body.message || body.error || res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export async function listSecrets(
  workspaceId: string,
): Promise<Secret[]> {
  const data = await request<Array<{ key: string; scope?: string; has_value?: boolean; created_at?: string; updated_at?: string }>>(apiUrl(workspaceId));
  // Platform returns flat array with { key, scope, has_value }
  // Transform to Secret[] format expected by the store
  if (!Array.isArray(data)) return [];
  return data.map((item) => ({
    name: item.key,
    masked_value: item.has_value ? '••••••••' : '',
    group: inferGroupFromKey(item.key) as Secret['group'],
    status: 'unverified' as const,
    updated_at: item.updated_at ?? '',
  }));
}

function inferGroupFromKey(key: string): string {
  if (key.startsWith('GITHUB')) return 'github';
  if (key.startsWith('ANTHROPIC') || key.startsWith('CLAUDE')) return 'anthropic';
  if (key.startsWith('OPENROUTER') || key.startsWith('OPENAI')) return 'openrouter';
  return 'custom';
}

export async function createSecret(
  workspaceId: string,
  name: string,
  value: string,
): Promise<Secret> {
  // Platform uses PUT /settings/secrets with {key, value}
  await request<unknown>(apiUrl(workspaceId), {
    method: 'PUT',
    body: JSON.stringify({ key: name, value }),
  });
  return { name, masked_value: '••••••••', group: inferGroupFromKey(name) as Secret['group'], status: 'unverified', updated_at: new Date().toISOString() };
}

export async function updateSecret(
  workspaceId: string,
  name: string,
  value: string,
): Promise<Secret> {
  await request<unknown>(apiUrl(workspaceId), {
    method: 'PUT',
    body: JSON.stringify({ key: name, value }),
  });
  return { name, masked_value: '••••••••', group: inferGroupFromKey(name) as Secret['group'], status: 'unverified', updated_at: new Date().toISOString() };
}

export async function deleteSecret(
  workspaceId: string,
  name: string,
): Promise<void> {
  return request<void>(apiUrl(workspaceId, `/${encodeURIComponent(name)}`), {
    method: 'DELETE',
  });
}

export async function validateSecret(
  provider: string,
  key: string,
): Promise<{ valid: boolean; error?: string }> {
  return request<{ valid: boolean; error?: string }>(
    `${PLATFORM_URL}/secrets/validate`,
    {
      method: 'POST',
      body: JSON.stringify({ provider, key }),
    },
  );
}

/**
 * Fetch the list of workspace IDs that depend on a given secret key.
 * Used by DeleteConfirmDialog to show impact.
 */
export async function fetchDependents(
  workspaceId: string,
  secretName: string,
): Promise<string[]> {
  const data = await request<{ dependents: string[] }>(
    apiUrl(workspaceId, `/${encodeURIComponent(secretName)}/dependents`),
  );
  return data.dependents;
}
