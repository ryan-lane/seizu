import { renderHook, act, waitFor } from '@testing-library/react';
import { AuthContext } from 'src/auth.context';
import { AuthConfigContext } from 'src/authConfig.context';
import { useQueryHistory } from 'src/hooks/useQueryHistory';

const AUTH_CONFIG_NO_OIDC = { auth_required: false, oidc: null, userManager: null };

function makeWrapper(authRequired: boolean, accessToken: string | null) {
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <AuthConfigContext.Provider value={{ ...AUTH_CONFIG_NO_OIDC, auth_required: authRequired }}>
        <AuthContext.Provider value={{ user: null, accessToken, isLoading: false }}>
          {children}
        </AuthContext.Provider>
      </AuthConfigContext.Provider>
    );
  };
}

const HISTORY_PAGE = {
  items: [
    { history_id: '1', user_id: 'u1', query: 'MATCH (n) RETURN n', executed_at: '2024-01-01T00:00:00Z' }
  ],
  total: 1,
  page: 1,
  per_page: 20
};

describe('useQueryHistory', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    Object.defineProperty(document, 'cookie', {
      writable: true,
      value: '_csrf_token=testtoken'
    });
  });

  it('does not fetch when auth_required and accessToken is null', () => {
    global.fetch = jest.fn();
    const { result } = renderHook(() => useQueryHistory(), {
      wrapper: makeWrapper(true, null)
    });
    act(() => {
      result.current.fetchHistory(1, 20);
    });
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('fetches with correct URL parameters', async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(HISTORY_PAGE)
    });
    const { result } = renderHook(() => useQueryHistory(), {
      wrapper: makeWrapper(false, null)
    });
    act(() => {
      result.current.fetchHistory(2, 10);
    });
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/v1/query-history?page=2&per_page=10',
      expect.any(Object)
    );
  });

  it('returns data on success', async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(HISTORY_PAGE)
    });
    const { result } = renderHook(() => useQueryHistory(), {
      wrapper: makeWrapper(false, null)
    });
    act(() => {
      result.current.fetchHistory(1, 20);
    });
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.data).toEqual(HISTORY_PAGE);
    expect(result.current.error).toBeNull();
  });

  it('sets error state on non-ok response', async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: () => Promise.resolve({})
    });
    const { result } = renderHook(() => useQueryHistory(), {
      wrapper: makeWrapper(false, null)
    });
    act(() => {
      result.current.fetchHistory(1, 20);
    });
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error).toBeInstanceOf(Error);
    expect(result.current.data).toBeNull();
  });

  it('sets error state on network failure', async () => {
    global.fetch = jest.fn().mockRejectedValue(new Error('Network error'));
    const { result } = renderHook(() => useQueryHistory(), {
      wrapper: makeWrapper(false, null)
    });
    act(() => {
      result.current.fetchHistory(1, 20);
    });
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error).toBeInstanceOf(Error);
    expect(result.current.data).toBeNull();
  });

  it('includes Authorization header when accessToken is set', async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(HISTORY_PAGE)
    });
    const { result } = renderHook(() => useQueryHistory(), {
      wrapper: makeWrapper(true, 'mytoken')
    });
    act(() => {
      result.current.fetchHistory(1, 20);
    });
    expect(global.fetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: 'Bearer mytoken' })
      })
    );
  });

  it('does not include Authorization header when no token', async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(HISTORY_PAGE)
    });
    const { result } = renderHook(() => useQueryHistory(), {
      wrapper: makeWrapper(false, null)
    });
    act(() => {
      result.current.fetchHistory(1, 20);
    });
    const headers = (global.fetch as jest.Mock).mock.calls[0][1].headers;
    expect(headers).not.toHaveProperty('Authorization');
  });

  it('sets loading: true while fetching', () => {
    let resolveFetch!: (v: unknown) => void;
    global.fetch = jest.fn().mockReturnValue(
      new Promise((res) => {
        resolveFetch = res;
      })
    );
    const { result } = renderHook(() => useQueryHistory(), {
      wrapper: makeWrapper(false, null)
    });
    act(() => {
      result.current.fetchHistory(1, 20);
    });
    expect(result.current.loading).toBe(true);
    // Clean up
    act(() => {
      resolveFetch({ ok: true, json: () => Promise.resolve(HISTORY_PAGE) });
    });
  });
});
