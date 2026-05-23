import { render, screen, waitFor, cleanup } from '@testing-library/react';
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

  it('does not auto-start login on the logged-out page', async () => {
    withMockLocation('http://test/logged-out');
    render(
      <AuthConfigContext.Provider value={AUTH_CONFIG_REQUIRED}>
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
    expect(beginLoginSpy).not.toHaveBeenCalled();
  });

  it('serializes refresh through the Web Locks API when available', async () => {
    const requestMock = jest.fn((_name: string, cb: () => Promise<unknown>) =>
      cb(),
    );
    Object.defineProperty(navigator, 'locks', {
      configurable: true,
      value: { request: requestMock },
    });
    refreshSpy.mockResolvedValue({
      access_token: 'AT-LOCK',
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

    await waitFor(() => {
      expect(screen.getByTestId('token').textContent).toBe('AT-LOCK');
    });
    expect(requestMock).toHaveBeenCalledWith(
      'seizu-auth-refresh',
      expect.any(Function),
    );

    // Restore the absent-by-default state so other tests exercise the fallback.
    Object.defineProperty(navigator, 'locks', {
      configurable: true,
      value: undefined,
    });
  });

  it('schedules a follow-up refresh ~30s before token expiry', async () => {
    // Don't try to *drive* the follow-up refresh — that requires manually
    // advancing fake timers, which deadlocks @testing-library's waitFor
    // (its polling can't progress) and starves React's scheduler. Instead,
    // let the mount refresh resolve via waitFor (which auto-advances fake
    // timers), then assert the follow-up timer was *scheduled* with the
    // right delay by inspecting the setTimeout spy.
    refreshSpy.mockResolvedValue({
      access_token: 'AT-1',
      expires_in: 300,
      token_type: 'Bearer',
    });
    const setTimeoutSpy = jest.spyOn(globalThis, 'setTimeout');

    render(
      <AuthConfigContext.Provider value={AUTH_CONFIG_REQUIRED}>
        <AuthProvider>
          <ChildThatReadsAuth />
        </AuthProvider>
      </AuthConfigContext.Provider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('token').textContent).toBe('AT-1');
    });

    // ttl(300s) - lead(30s) = 270s → 270_000ms.
    const scheduledDelays = setTimeoutSpy.mock.calls.map((call) => call[1]);
    expect(scheduledDelays).toContain(270_000);

    setTimeoutSpy.mockRestore();
  });
});
