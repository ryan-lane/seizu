import { render, screen, waitFor, act, cleanup } from '@testing-library/react';
import { useContext, type ReactElement } from 'react';
import * as authClient from 'src/api/authClient';
import { AuthContext } from 'src/auth.context';
import { AuthConfigContext } from 'src/authConfig.context';
import AuthProvider, {
  _resetInflightRefreshForTests,
} from 'src/components/AuthProvider';

const AUTH_CONFIG_REQUIRED = {
  auth_required: true,
  oidc: null,
};

const AUTH_CONFIG_DISABLED = {
  auth_required: false,
  oidc: null,
};

function ChildThatReadsAuth(): ReactElement {
  const { accessToken, isLoading } = useContext(AuthContext);
  return (
    <div>
      <span data-testid="token">{accessToken ?? 'NO_TOKEN'}</span>
      <span data-testid="loading">{isLoading ? 'LOADING' : 'READY'}</span>
    </div>
  );
}

// Flush several microtask rounds — enough to settle the refresh promise,
// its .finally() dedup reset, and the resulting React state update.
async function flushMicrotasks(): Promise<void> {
  for (let i = 0; i < 5; i += 1) {
    await Promise.resolve();
  }
}

const originalLocation = window.location;
let refreshSpy: jest.SpyInstance;
let beginLoginSpy: jest.SpyInstance;

function withMockLocation(href: string): jest.Mock {
  const url = new URL(href);
  const assignMock = jest.fn();
  Object.defineProperty(window, 'location', {
    configurable: true,
    value: {
      ...originalLocation,
      assign: assignMock,
      href,
      origin: url.origin,
      pathname: url.pathname,
      search: url.search,
      hash: url.hash,
    },
  });
  return assignMock;
}

describe('AuthProvider', () => {
  beforeEach(() => {
    jest.useFakeTimers();
    _resetInflightRefreshForTests();
    refreshSpy = jest.spyOn(authClient, 'refreshSession');
    beginLoginSpy = jest.spyOn(authClient, 'beginLogin');
  });

  afterEach(() => {
    cleanup();
    jest.useRealTimers();
    refreshSpy.mockRestore();
    beginLoginSpy.mockRestore();
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: originalLocation,
    });
  });

  it('shows nothing while loading and renders children once refresh succeeds', async () => {
    refreshSpy.mockResolvedValue({
      access_token: 'AT-1',
      expires_in: 300,
      token_type: 'Bearer',
    });

    render(
      <AuthConfigContext.Provider value={AUTH_CONFIG_REQUIRED}>
        <AuthProvider>
          <ChildThatReadsAuth />
        </AuthProvider>
      </AuthConfigContext.Provider>,
    );

    expect(screen.queryByTestId('token')).toBeNull();
    await waitFor(() => {
      expect(screen.getByTestId('token').textContent).toBe('AT-1');
    });
    expect(screen.getByTestId('loading').textContent).toBe('READY');
    expect(refreshSpy).toHaveBeenCalledTimes(1);
  });

  it('renders children immediately when auth is disabled', async () => {
    render(
      <AuthConfigContext.Provider value={AUTH_CONFIG_DISABLED}>
        <AuthProvider>
          <ChildThatReadsAuth />
        </AuthProvider>
      </AuthConfigContext.Provider>,
    );
    await waitFor(() => {
      expect(screen.getByTestId('loading').textContent).toBe('READY');
    });
    expect(screen.getByTestId('token').textContent).toBe('NO_TOKEN');
    expect(refreshSpy).not.toHaveBeenCalled();
  });

  it('redirects to the IDP authorize URL when refresh fails', async () => {
    const assignMock = withMockLocation('http://test/reports/abc?x=1');
    refreshSpy.mockRejectedValue(
      new authClient.AuthRequestError(401, 'Session expired'),
    );
    beginLoginSpy.mockResolvedValue({
      authorize_url: 'http://idp/authorize?state=xyz',
    });

    render(
      <AuthConfigContext.Provider value={AUTH_CONFIG_REQUIRED}>
        <AuthProvider>
          <ChildThatReadsAuth />
        </AuthProvider>
      </AuthConfigContext.Provider>,
    );

    await waitFor(() => {
      expect(beginLoginSpy).toHaveBeenCalledWith('/reports/abc?x=1');
    });
    await waitFor(() => {
      expect(assignMock).toHaveBeenCalledWith('http://idp/authorize?state=xyz');
    });
  });

  it('schedules a follow-up refresh ~30s before expiry', async () => {
    refreshSpy.mockResolvedValue({
      access_token: 'AT-1',
      expires_in: 300,
      token_type: 'Bearer',
    });

    render(
      <AuthConfigContext.Provider value={AUTH_CONFIG_REQUIRED}>
        <AuthProvider>
          <ChildThatReadsAuth />
        </AuthProvider>
      </AuthConfigContext.Provider>,
    );

    // NB: with fake timers active, @testing-library's waitFor can deadlock
    // once we manually advance the clock — its polling can't make progress.
    // Drive the async refresh deterministically via explicit microtask
    // flushing instead. The flush must outlast the dedup chain
    // (refreshSession → .finally clears inflightRefresh) so the next tick
    // issues a fresh call rather than reusing the resolved promise.
    await act(async () => {
      await flushMicrotasks();
    });
    expect(refreshSpy).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId('token').textContent).toBe('AT-1');

    // ttl(300s) - lead(30s) = 270s. Just before the boundary: no new call.
    await act(async () => {
      jest.advanceTimersByTime(269_000);
      await flushMicrotasks();
    });
    expect(refreshSpy).toHaveBeenCalledTimes(1);

    // Crossing 270s fires the scheduled refresh.
    await act(async () => {
      jest.advanceTimersByTime(2_000);
      await flushMicrotasks();
    });
    expect(refreshSpy).toHaveBeenCalledTimes(2);
  });
});
