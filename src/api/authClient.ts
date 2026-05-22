// Thin wrapper around the backend BFF auth endpoints.
//
// These functions are the only ones that talk to the cookie-authenticated
// /api/v1/auth/* routes. All other API hooks use Bearer auth via the access
// token in React state (see AuthContext), so they don't need this module.

const CSRF_HEADER = 'X-Seizu-Csrf';

export interface LoginResponse {
  authorize_url: string;
}

export interface RefreshResponse {
  access_token: string;
  expires_in: number | null;
  token_type: string;
}

export interface LogoutResponse {
  post_logout_url: string | null;
}

export class AuthRequestError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = 'AuthRequestError';
  }
}

async function readErrorMessage(res: Response): Promise<string> {
  try {
    const body = (await res.json()) as { error?: string };
    if (body.error) return body.error;
  } catch {
    // body wasn't JSON; fall through
  }
  return `HTTP ${res.status}`;
}

/**
 * Start an OIDC login flow. Returns the authorize URL the browser should
 * top-level-navigate to. `returnTo` is round-tripped through the IDP and
 * the user lands back on it after callback. Must be a same-origin path.
 */
export async function beginLogin(returnTo: string): Promise<LoginResponse> {
  const params = new URLSearchParams({ return_to: returnTo });
  const res = await fetch(`/api/v1/auth/login?${params}`, {
    method: 'GET',
    credentials: 'same-origin',
  });
  if (!res.ok) {
    throw new AuthRequestError(res.status, await readErrorMessage(res));
  }
  return (await res.json()) as LoginResponse;
}

/**
 * Use the session cookie to mint a fresh access token. Re-issues the cookie
 * with a rolling Max-Age. Throws on any non-2xx; in particular, 401 means
 * the session is gone and the caller should redirect to login.
 */
export async function refreshSession(): Promise<RefreshResponse> {
  const res = await fetch('/api/v1/auth/refresh', {
    method: 'POST',
    credentials: 'same-origin',
    headers: { [CSRF_HEADER]: '1' },
  });
  if (!res.ok) {
    throw new AuthRequestError(res.status, await readErrorMessage(res));
  }
  return (await res.json()) as RefreshResponse;
}

/**
 * Clear the session cookie and (server-side, best-effort) revoke the refresh token.
 * Always succeeds from the client's perspective — backend swallows IDP errors.
 */
export async function logout(): Promise<LogoutResponse> {
  const res = await fetch('/api/v1/auth/logout', {
    method: 'POST',
    credentials: 'same-origin',
    headers: { [CSRF_HEADER]: '1' },
  });
  if (!res.ok) {
    throw new AuthRequestError(res.status, await readErrorMessage(res));
  }
  return (await res.json()) as LogoutResponse;
}
