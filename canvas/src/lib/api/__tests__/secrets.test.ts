import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';

// Set PLATFORM_URL before importing
vi.stubEnv('NEXT_PUBLIC_PLATFORM_URL', 'http://localhost:8080');

// Must import after env stub
const secretsModule = await import('../secrets');
const {
  listSecrets,
  createSecret,
  updateSecret,
  deleteSecret,
  validateSecret,
  fetchDependents,
  ApiError,
} = secretsModule;

// ── Helpers ──────────────────────────────────────────────────────

const WS_ID = 'ws-test-1';

function mockFetch(body: unknown, status = 200) {
  return vi.fn(() =>
    Promise.resolve({
      ok: status >= 200 && status < 300,
      status,
      statusText: status === 200 ? 'OK' : 'Error',
      json: () => Promise.resolve(body),
    } as Response),
  );
}

function mockFetch204() {
  return vi.fn(() =>
    Promise.resolve({
      ok: true,
      status: 204,
      statusText: 'No Content',
      json: () => Promise.reject(new Error('No body')),
    } as Response),
  );
}

// ── Tests ────────────────────────────────────────────────────────

describe('secrets API client', () => {
  const originalFetch = global.fetch;

  afterEach(() => {
    global.fetch = originalFetch;
  });

  describe('listSecrets', () => {
    it('sends GET to /workspaces/{id}/secrets', async () => {
      const secrets = [
        { name: 'KEY', masked_value: '••••', group: 'github', status: 'unverified', updated_at: '' },
      ];
      global.fetch = mockFetch({ secrets });

      const result = await listSecrets(WS_ID);

      expect(global.fetch).toHaveBeenCalledWith(
        `http://localhost:8080/workspaces/${WS_ID}/secrets`,
        expect.objectContaining({
          headers: expect.objectContaining({
            'Content-Type': 'application/json',
          }),
        }),
      );
      expect(result).toEqual(secrets);
    });

    it('throws ApiError on non-OK response', async () => {
      global.fetch = mockFetch({ message: 'Unauthorized' }, 401);

      await expect(listSecrets(WS_ID)).rejects.toThrow(ApiError);
      await expect(listSecrets(WS_ID)).rejects.toThrow('Unauthorized');
    });
  });

  describe('createSecret', () => {
    it('sends POST with name and value', async () => {
      const created = { name: 'KEY', masked_value: '••••', group: 'custom', status: 'unverified', updated_at: '' };
      global.fetch = mockFetch(created);

      const result = await createSecret(WS_ID, 'KEY', 'mysecretval');

      expect(global.fetch).toHaveBeenCalledWith(
        `http://localhost:8080/workspaces/${WS_ID}/secrets`,
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ name: 'KEY', value: 'mysecretval' }),
        }),
      );
      expect(result).toEqual(created);
    });
  });

  describe('updateSecret', () => {
    it('sends PUT to /workspaces/{id}/secrets/{name}', async () => {
      const updated = { name: 'KEY', masked_value: '••••new', group: 'custom', status: 'unverified', updated_at: '' };
      global.fetch = mockFetch(updated);

      const result = await updateSecret(WS_ID, 'KEY', 'newval');

      expect(global.fetch).toHaveBeenCalledWith(
        `http://localhost:8080/workspaces/${WS_ID}/secrets/KEY`,
        expect.objectContaining({
          method: 'PUT',
          body: JSON.stringify({ value: 'newval' }),
        }),
      );
      expect(result).toEqual(updated);
    });

    it('encodes special characters in secret name', async () => {
      global.fetch = mockFetch({});

      await updateSecret(WS_ID, 'MY KEY/SPECIAL', 'val');

      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining(encodeURIComponent('MY KEY/SPECIAL')),
        expect.anything(),
      );
    });
  });

  describe('deleteSecret', () => {
    it('sends DELETE and handles 204', async () => {
      global.fetch = mockFetch204();

      await expect(deleteSecret(WS_ID, 'KEY')).resolves.toBeUndefined();

      expect(global.fetch).toHaveBeenCalledWith(
        `http://localhost:8080/workspaces/${WS_ID}/secrets/KEY`,
        expect.objectContaining({ method: 'DELETE' }),
      );
    });
  });

  describe('validateSecret', () => {
    it('sends POST to /secrets/validate', async () => {
      global.fetch = mockFetch({ valid: true });

      const result = await validateSecret('github', 'ghp_abc');

      expect(global.fetch).toHaveBeenCalledWith(
        'http://localhost:8080/secrets/validate',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ provider: 'github', key: 'ghp_abc' }),
        }),
      );
      expect(result).toEqual({ valid: true });
    });

    it('returns error detail on invalid key', async () => {
      global.fetch = mockFetch({ valid: false, error: 'Key expired' });

      const result = await validateSecret('github', 'expired-key');
      expect(result.valid).toBe(false);
      expect(result.error).toBe('Key expired');
    });
  });

  describe('fetchDependents', () => {
    it('returns list of dependent workspace names', async () => {
      global.fetch = mockFetch({ dependents: ['ws-a', 'ws-b'] });

      const result = await fetchDependents(WS_ID, 'GITHUB_TOKEN');

      expect(global.fetch).toHaveBeenCalledWith(
        `http://localhost:8080/workspaces/${WS_ID}/secrets/GITHUB_TOKEN/dependents`,
        expect.anything(),
      );
      expect(result).toEqual(['ws-a', 'ws-b']);
    });
  });

  describe('ApiError', () => {
    it('has status and message', () => {
      const err = new ApiError(404, 'Not found');
      expect(err.status).toBe(404);
      expect(err.message).toBe('Not found');
      expect(err.name).toBe('ApiError');
      expect(err instanceof Error).toBe(true);
    });
  });
});
