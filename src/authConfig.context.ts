import { createContext } from 'react';

export interface AuthConfig {
  auth_required: boolean;
}

// Default to requiring auth so queries wait for a token until the real
// value arrives from the config endpoint.
export const AuthConfigContext = createContext<AuthConfig>({ auth_required: true });
