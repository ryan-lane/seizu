import {
  AuthRequestError,
  beginLogin,
  logout,
  refreshSession,
} from 'src/api/authClient';

describe('beginLogin', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('GETs /api/v1/auth/login with the return_to query param and returns the body', async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({ authorize_url: 'http://idp/authorize?x=1' }),
    });
    const result = await beginLogin('/reports/abc');
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/v1/auth/login?return_to=%2Freports%2Fabc',
      expect.objectContaining({
        method: 'GET',
        credentials: 'same-origin',
      }),
    );
    expect(result.authorize_url).toBe('http://idp/authorize?x=1');
  });

  it('throws AuthRequestError on non-2xx', async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 503,
      json: () => Promise.resolve({ error: 'OIDC provider unavailable' }),
    });
    await expect(beginLogin('/')).rejects.toMatchObject({
      name: 'AuthRequestError',
      status: 503,
      message: 'OIDC provider unavailable',
    });
  });
});

describe('refreshSession', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('POSTs /api/v1/auth/refresh with the CSRF header and returns the token response', async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          access_token: 'at-1',
          expires_in: 300,
          token_type: 'Bearer',
        }),
    });
    const result = await refreshSession();
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/v1/auth/refresh',
      expect.objectContaining({
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'X-Seizu-Csrf': '1' },
      }),
    );
    expect(result.access_token).toBe('at-1');
    expect(result.expires_in).toBe(300);
  });

  it('throws AuthRequestError with status 401 when the session is gone', async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: () => Promise.resolve({ error: 'Session expired' }),
    });
    expect.assertions(3);
    try {
      await refreshSession();
    } catch (err) {
      expect(err).toBeInstanceOf(AuthRequestError);
      expect((err as AuthRequestError).status).toBe(401);
      expect((err as AuthRequestError).message).toBe('Session expired');
    }
  });

  it('falls back to a generic message when the error body is not JSON', async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: () => Promise.reject(new Error('not json')),
    });
    expect.assertions(1);
    try {
      await refreshSession();
    } catch (err) {
      expect((err as AuthRequestError).message).toBe('HTTP 500');
    }
  });
});

describe('logout', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('POSTs /api/v1/auth/logout with the CSRF header', async () => {
    global.fetch = jest
      .fn()
      .mockResolvedValue({ ok: true, json: () => Promise.resolve(null) });
    await logout();
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/v1/auth/logout',
      expect.objectContaining({
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'X-Seizu-Csrf': '1' },
      }),
    );
  });

  it('throws AuthRequestError on non-2xx', async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 403,
      json: () => Promise.resolve({ error: 'Missing CSRF header' }),
    });
    await expect(logout()).rejects.toMatchObject({
      name: 'AuthRequestError',
      status: 403,
    });
  });
});
