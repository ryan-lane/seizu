import { UserManager, type UserManagerSettings } from 'oidc-client-ts';

function createUserManager(): UserManager | null {
  if (process.env.REACT_APP_OIDC_ENABLED !== 'true') {
    return null;
  }
  const authority = process.env.REACT_APP_OIDC_AUTHORITY;
  const clientId = process.env.REACT_APP_OIDC_CLIENT_ID;
  const redirectUri = process.env.REACT_APP_OIDC_REDIRECT_URI;
  if (!authority || !clientId || !redirectUri) {
    console.warn(
      'OIDC is enabled but REACT_APP_OIDC_AUTHORITY, REACT_APP_OIDC_CLIENT_ID, ' +
        'or REACT_APP_OIDC_REDIRECT_URI is not set.'
    );
    return null;
  }
  const settings: UserManagerSettings = {
    authority,
    client_id: clientId,
    redirect_uri: redirectUri,
    scope: process.env.REACT_APP_OIDC_SCOPE || 'openid email',
    response_type: 'code'
  };
  return new UserManager(settings);
}

export const userManager = createUserManager();
