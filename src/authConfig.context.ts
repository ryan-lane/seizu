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
}

// Default to requiring auth so queries wait for a token until the real
// value arrives from the config endpoint.
export const AuthConfigContext = createContext<AuthConfig>({
  auth_required: true,
  oidc: null,
});
