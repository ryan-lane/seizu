import { ReactNode, useState, useEffect, useContext } from 'react';
import type { User } from 'oidc-client-ts';
import { AuthContext } from 'src/auth.context';
import { AuthConfigContext } from 'src/authConfig.context';

// Paths that should never trigger an OIDC redirect, even when unauthenticated.
const UNAUTHENTICATED_PATHS = ['/auth/callback'];

interface AuthProviderProps {
  children: ReactNode;
}

function AuthProvider({ children }: AuthProviderProps) {
  const { userManager } = useContext(AuthConfigContext);
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(userManager !== null);

  useEffect(() => {
    if (!userManager) {
      return;
    }

    const onUserLoaded = (loadedUser: User) => {
      setUser(loadedUser);
      setIsLoading(false);
    };
    const onUserUnloaded = () => setUser(null);

    userManager.events.addUserLoaded(onUserLoaded);
    userManager.events.addUserUnloaded(onUserUnloaded);

    // On the OIDC callback path, OidcCallback drives the flow via
    // signinRedirectCallback(). The userLoaded event above will fire when it
    // completes — don't try to load or redirect here.
    if (UNAUTHENTICATED_PATHS.includes(window.location.pathname)) {
      setIsLoading(false);
    } else {
      userManager.getUser().then((loadedUser) => {
        if (loadedUser && !loadedUser.expired) {
          setUser(loadedUser);
          setIsLoading(false);
        } else {
          // Redirect to OIDC; page will leave so we stay in loading state.
          userManager.signinRedirect();
        }
      });
    }

    return () => {
      userManager.events.removeUserLoaded(onUserLoaded);
      userManager.events.removeUserUnloaded(onUserUnloaded);
    };
  }, [userManager]);

  const accessToken = user?.access_token ?? null;

  return (
    <AuthContext.Provider value={{ user, accessToken, isLoading }}>
      {isLoading ? null : children}
    </AuthContext.Provider>
  );
}

export default AuthProvider;
