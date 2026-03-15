import { renderHook, act } from '@testing-library/react';
import { useState } from 'react';
import { AuthContext } from 'src/auth.context';
import { AuthConfigContext } from 'src/authConfig.context';
import { useLazyCypherQuery } from 'src/hooks/useCypherQuery';

const CYPHER = 'MATCH (n) RETURN n';

function makeWrapper(authRequired: boolean, accessToken: string | null) {
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <AuthConfigContext.Provider value={{ auth_required: authRequired }}>
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
    <AuthConfigContext.Provider value={{ auth_required: true }}>
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
    // CSRF cookie
    Object.defineProperty(document, 'cookie', {
      writable: true,
      value: '_csrf_token=testtoken'
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
      '/api/v1/query',
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
});
