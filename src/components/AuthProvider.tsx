import { ReactNode, useState, useEffect, useContext } from 'react';
import {
  beginLogin,
  refreshSession,
  type RefreshResponse,
} from 'src/api/authClient';
import { AuthContext } from 'src/auth.context';
import { AuthConfigContext } from 'src/authConfig.context';

// Module-level dedup of in-flight refreshes. React StrictMode double-mounts
// effects in dev, which would fire two /auth/refresh calls in parallel — and
// since Authentik rotates refresh tokens, the second call would race the
// first and get 401 from a now-rotated cookie. Sharing one in-flight promise
// across concurrent callers eliminates the race.
let inflightRefresh: Promise<RefreshResponse> | null = null;

function refreshOnce(): Promise<RefreshResponse> {
  if (!inflightRefresh) {
    inflightRefresh = refreshSession().finally(() => {
      inflightRefresh = null;
    });
  }
  return inflightRefresh;
}

// Reset hook for tests — concurrent module state would otherwise leak
// between test cases.
export function _resetInflightRefreshForTests(): void {
  inflightRefresh = null;
}

const REFRESH_LEAD_TIME_SECONDS = 30;
const REFRESH_LEAD_TIME_FLOOR_MS = 5_000;
const DEFAULT_ACCESS_TOKEN_TTL_SECONDS = 300;

interface AuthProviderProps {
  children: ReactNode;
}

function AuthProvider({ children }: AuthProviderProps) {
  const { auth_required } = useContext(AuthConfigContext);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(auth_required);

  useEffect(() => {
    if (!auth_required) {
      setIsLoading(false);
      return;
    }

    let cancelled = false;
    let refreshTimer: ReturnType<typeof setTimeout> | null = null;

    async function tick(): Promise<void> {
      try {
        const { access_token, expires_in } = await refreshOnce();
        if (cancelled) return;
        setAccessToken(access_token);
        setIsLoading(false);
        const ttl = expires_in ?? DEFAULT_ACCESS_TOKEN_TTL_SECONDS;
        const delay = Math.max(
          REFRESH_LEAD_TIME_FLOOR_MS,
          (ttl - REFRESH_LEAD_TIME_SECONDS) * 1000,
        );
        refreshTimer = setTimeout(() => {
          void tick();
        }, delay);
      } catch {
        if (cancelled) return;
        const returnTo =
          window.location.pathname +
          window.location.search +
          window.location.hash;
        try {
          const { authorize_url } = await beginLogin(returnTo);
          window.location.assign(authorize_url);
        } catch {
          // IDP unreachable — leave the user on the loading state. There's
          // no useful programmatic recovery from this; ops needs to fix the
          // IDP.
        }
      }
    }

    void tick();

    return () => {
      cancelled = true;
      if (refreshTimer !== null) clearTimeout(refreshTimer);
    };
  }, [auth_required]);

  return (
    <AuthContext.Provider value={{ accessToken, isLoading }}>
      {isLoading ? null : children}
    </AuthContext.Provider>
  );
}

export default AuthProvider;
