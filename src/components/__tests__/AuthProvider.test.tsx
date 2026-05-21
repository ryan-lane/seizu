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
    refreshSpy
      .mockResolvedValueOnce({
        access_token: 'AT-1',
        expires_in: 300,
        token_type: 'Bearer',
      })
      .mockResolvedValueOnce({
        access_token: 'AT-2',
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
      expect(screen.getByTestId('token').textContent).toBe('AT-1');
    });

    // Lead time is 30s; with expires_in=300 the next refresh fires at 270_000 ms.
    await act(async () => {
      jest.advanceTimersByTime(270_000);
    });
    await waitFor(() => {
      expect(screen.getByTestId('token').textContent).toBe('AT-2');
    });
    expect(refreshSpy).toHaveBeenCalledTimes(2);
  });
});
