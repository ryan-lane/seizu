import { ReactNode, useState, useEffect } from 'react';
import type { User } from 'oidc-client-ts';
import { AuthContext } from 'src/auth.context';
import { userManager } from 'src/userManager';

// Paths that should never trigger an OIDC redirect, even when unauthenticated.
const UNAUTHENTICATED_PATHS = ['/auth/callback'];

interface AuthProviderProps {
  children: ReactNode;
}

function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(userManager !== null);

  useEffect(() => {
    if (!userManager) {
      return;
    }

    // Don't redirect when we're processing the OIDC callback.
    if (UNAUTHENTICATED_PATHS.includes(window.location.pathname)) {
      setIsLoading(false);
      return;
    }

    userManager.getUser().then((loadedUser) => {
      if (loadedUser && !loadedUser.expired) {
        setUser(loadedUser);
        setIsLoading(false);
      } else {
        // Redirect to OIDC; page will leave so we stay in loading state.
        userManager.signinRedirect();
      }
    });

    const onUserLoaded = (loadedUser: User) => {
      setUser(loadedUser);
      setIsLoading(false);
    };
    const onUserUnloaded = () => setUser(null);

    userManager.events.addUserLoaded(onUserLoaded);
    userManager.events.addUserUnloaded(onUserUnloaded);

    return () => {
      userManager.events.removeUserLoaded(onUserLoaded);
      userManager.events.removeUserUnloaded(onUserUnloaded);
    };
  }, []);

  const accessToken = user?.access_token ?? null;

  return (
    <AuthContext.Provider value={{ user, accessToken, isLoading }}>
      {isLoading ? null : children}
    </AuthContext.Provider>
  );
}

export default AuthProvider;
