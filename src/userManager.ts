import { UserManager, type UserManagerSettings } from 'oidc-client-ts';
import type { OidcConfig } from 'src/authConfig.context';

export function createUserManager(config: OidcConfig): UserManager {
  const settings: UserManagerSettings = {
    authority: config.authority,
    client_id: config.client_id,
    // Always use the current browser origin so the OIDC callback returns to
    // the same origin that initiated the flow. Using a hardcoded redirect_uri
    // from the backend config causes a cross-origin sessionStorage miss when
    // the app is accessed on a different port (e.g. :8080 vs :3000).
    redirect_uri: `${window.location.origin}/auth/callback`,
    scope: config.scope,
    response_type: 'code'
  };
  return new UserManager(settings);
}
