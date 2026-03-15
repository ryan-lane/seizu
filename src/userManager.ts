import { UserManager, type UserManagerSettings } from 'oidc-client-ts';
import type { OidcConfig } from 'src/authConfig.context';

export function createUserManager(config: OidcConfig): UserManager {
  const settings: UserManagerSettings = {
    authority: config.authority,
    client_id: config.client_id,
    redirect_uri: config.redirect_uri,
    scope: config.scope,
    response_type: 'code'
  };
  return new UserManager(settings);
}
