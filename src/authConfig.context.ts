import { createContext } from 'react';

export interface OidcConfig {
  authority: string;
  client_id: string;
  redirect_uri: string;
  scope: string;
}

export interface AuthConfig {
  auth_required: boolean;
  oidc: OidcConfig | null;
  // False until GET /api/v1/config resolves. Data hooks can safely act on the
  // optimistic auth_required:true default (they just hold requests until a
  // token exists), but AuthProvider must wait for this to flip true before
  // bootstrapping a login flow — acting early would hit /auth/refresh and
  // /auth/login on a server that may have auth disabled.
  loaded: boolean;
}

// Default to requiring auth so queries wait for a token until the real
// value arrives from the config endpoint.
export const AuthConfigContext = createContext<AuthConfig>({
  auth_required: true,
  oidc: null,
  loaded: false,
});
