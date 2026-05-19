import { renderHook, act, waitFor } from '@testing-library/react';
import { AuthContext } from 'src/auth.context';
import { AuthConfigContext } from 'src/authConfig.context';
import { useGraphSchema } from 'src/hooks/useGraphSchema';

const AUTH_CONFIG_NO_OIDC = {
  auth_required: false,
  oidc: null,
  userManager: null,
};

function makeWrapper(authRequired: boolean, accessToken: string | null) {
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <AuthConfigContext.Provider
        value={{ ...AUTH_CONFIG_NO_OIDC, auth_required: authRequired }}
      >
        <AuthContext.Provider
          value={{ user: null, accessToken, isLoading: false }}
        >
          {children}
        </AuthContext.Provider>
      </AuthConfigContext.Provider>
    );
  };
}

const SCHEMA_RESPONSE = {
  labels: ['Person', 'Repo'],
  relationship_types: ['OWNS', 'CONTRIBUTES_TO'],
  property_keys: ['name', 'email'],
};

describe('useGraphSchema', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('does not fetch when auth_required and accessToken is null', () => {
    global.fetch = jest.fn();
    const { result } = renderHook(() => useGraphSchema(), {
      wrapper: makeWrapper(true, null),
    });
    act(() => {
      result.current.fetchSchema();
    });
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('fetches from /api/v1/graph/schema', () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(SCHEMA_RESPONSE),
    });
    const { result } = renderHook(() => useGraphSchema(), {
      wrapper: makeWrapper(false, null),
    });
    act(() => {
      result.current.fetchSchema();
    });
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/v1/graph/schema',
      expect.any(Object),
    );
  });

  it('returns schema data on success', async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(SCHEMA_RESPONSE),
    });
    const { result } = renderHook(() => useGraphSchema(), {
      wrapper: makeWrapper(false, null),
    });
    act(() => {
      result.current.fetchSchema();
    });
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.schema).toEqual(SCHEMA_RESPONSE);
    expect(result.current.error).toBeNull();
  });

  it('sets error on non-ok response', async () => {
    global.fetch = jest.fn().mockResolvedValue({ ok: false, status: 500 });
    const { result } = renderHook(() => useGraphSchema(), {
      wrapper: makeWrapper(false, null),
    });
    act(() => {
      result.current.fetchSchema();
    });
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error).toBeInstanceOf(Error);
    expect(result.current.schema).toBeNull();
  });

  it('sets error on network failure', async () => {
    global.fetch = jest.fn().mockRejectedValue(new Error('Network error'));
    const { result } = renderHook(() => useGraphSchema(), {
      wrapper: makeWrapper(false, null),
    });
    act(() => {
      result.current.fetchSchema();
    });
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error).toBeInstanceOf(Error);
    expect(result.current.schema).toBeNull();
  });

  it('includes Authorization header when accessToken is set', () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(SCHEMA_RESPONSE),
    });
    const { result } = renderHook(() => useGraphSchema(), {
      wrapper: makeWrapper(true, 'tok-abc'),
    });
    act(() => {
      result.current.fetchSchema();
    });
    expect(global.fetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: 'Bearer tok-abc' }),
      }),
    );
  });

  it('does not include Authorization header when no token', async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(SCHEMA_RESPONSE),
    });
    const { result } = renderHook(() => useGraphSchema(), {
      wrapper: makeWrapper(false, null),
    });
    act(() => {
      result.current.fetchSchema();
    });
    const headers = (global.fetch as jest.Mock).mock.calls[0][1].headers;
    expect(headers).not.toHaveProperty('Authorization');
  });

  it('sets loading: true while fetching', () => {
    let resolveFetch!: (v: unknown) => void;
    global.fetch = jest.fn().mockReturnValue(
      new Promise((res) => {
        resolveFetch = res;
      }),
    );
    const { result } = renderHook(() => useGraphSchema(), {
      wrapper: makeWrapper(false, null),
    });
    act(() => {
      result.current.fetchSchema();
    });
    expect(result.current.loading).toBe(true);
    act(() => {
      resolveFetch({ ok: true, json: () => Promise.resolve(SCHEMA_RESPONSE) });
    });
  });

  it('fetches without auth when auth not required and no token', () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(SCHEMA_RESPONSE),
    });
    const { result } = renderHook(() => useGraphSchema(), {
      wrapper: makeWrapper(false, null),
    });
    act(() => {
      result.current.fetchSchema();
    });
    expect(global.fetch).toHaveBeenCalledTimes(1);
  });
});
