import { renderHook, act } from '@testing-library/react';
import { useState } from 'react';
import { AuthContext } from 'src/auth.context';
import { AuthConfigContext } from 'src/authConfig.context';
import { useLazyCypherQuery } from 'src/hooks/useCypherQuery';

const CYPHER = 'MATCH (n) RETURN n';

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

// Stateful wrapper that allows updating auth values after initial render.
let _setToken: ((t: string | null) => void) | null = null;
function StatefulWrapper({ children }: { children: React.ReactNode }) {
  const [accessToken, setToken] = useState<string | null>(null);
  _setToken = setToken;
  return (
    <AuthConfigContext.Provider value={{ ...AUTH_CONFIG_NO_OIDC, auth_required: true }}>
      <AuthContext.Provider value={{ user: null, accessToken, isLoading: false }}>
        {children}
      </AuthContext.Provider>
    </AuthConfigContext.Provider>
  );
}

describe('useLazyCypherQuery', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    global.fetch = jest.fn().mockResolvedValue({
      json: () => Promise.resolve({ results: [] })
    });
  });

  it('does not fetch when auth_required and accessToken is null', () => {
    const { result } = renderHook(() => useLazyCypherQuery(CYPHER), {
      wrapper: makeWrapper(true, null)
    });
    const [run] = result.current;
    act(() => {
      run();
    });
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('fetches with Authorization header when auth_required and accessToken is set', () => {
    const { result } = renderHook(() => useLazyCypherQuery(CYPHER), {
      wrapper: makeWrapper(true, 'mytoken')
    });
    const [run] = result.current;
    act(() => {
      run();
    });
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/v1/query/adhoc',
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: 'Bearer mytoken' })
      })
    );
  });

  it('fetches without Authorization header when auth not required', () => {
    const { result } = renderHook(() => useLazyCypherQuery(CYPHER), {
      wrapper: makeWrapper(false, null)
    });
    const [run] = result.current;
    act(() => {
      run();
    });
    expect(global.fetch).toHaveBeenCalled();
    const headers = (global.fetch as jest.Mock).mock.calls[0][1].headers;
    expect(headers).not.toHaveProperty('Authorization');
  });

  it('includes params in the request body', () => {
    const { result } = renderHook(() => useLazyCypherQuery(CYPHER), {
      wrapper: makeWrapper(false, null)
    });
    const [run] = result.current;
    act(() => {
      run({ base_severity: 'CRITICAL', count: 3 });
    });
    const body = JSON.parse((global.fetch as jest.Mock).mock.calls[0][1].body);
    expect(body.query).toBe(CYPHER);
    expect(body.params).toEqual({ base_severity: 'CRITICAL', count: 3 });
  });

  it('sends query without params when run is called with no arguments', () => {
    const { result } = renderHook(() => useLazyCypherQuery(CYPHER), {
      wrapper: makeWrapper(false, null)
    });
    const [run] = result.current;
    act(() => {
      run();
    });
    const body = JSON.parse((global.fetch as jest.Mock).mock.calls[0][1].body);
    expect(body.query).toBe(CYPHER);
    expect(body.params).toBeUndefined();
  });

  it('re-fires query when accessToken becomes available', () => {
    const { result } = renderHook(() => useLazyCypherQuery(CYPHER), {
      wrapper: StatefulWrapper
    });
    act(() => {
      result.current[0]();
    });
    expect(global.fetch).not.toHaveBeenCalled();

    // Simulate token arriving by updating the stateful wrapper's state.
    act(() => {
      _setToken!('newtoken');
    });
    act(() => {
      result.current[0]();
    });
    expect(global.fetch).toHaveBeenCalledTimes(1);
  });

  it('omits save_history for ad hoc queries', () => {
    const { result } = renderHook(() => useLazyCypherQuery(CYPHER), {
      wrapper: makeWrapper(false, null)
    });
    const [run] = result.current;
    act(() => {
      run();
    });
    const body = JSON.parse((global.fetch as jest.Mock).mock.calls[0][1].body);
    expect(body.save_history).toBeUndefined();
  });

  it('uses the signed report endpoint when a report token is provided', () => {
    const { result } = renderHook(() => useLazyCypherQuery(CYPHER, 'signed-token'), {
      wrapper: makeWrapper(false, null)
    });
    const [run] = result.current;
    act(() => {
      run({ base_severity: 'HIGH' });
    });
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/v1/query/report',
      expect.objectContaining({
        body: JSON.stringify({ token: 'signed-token', params: { base_severity: 'HIGH' } })
      })
    );
  });
});
