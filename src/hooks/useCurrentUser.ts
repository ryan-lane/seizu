import { createContext, createElement, useState, useEffect, useContext, ReactNode } from 'react';
import { AuthContext } from 'src/auth.context';
import { AuthConfigContext } from 'src/authConfig.context';

export interface CurrentUser {
  user_id: string;
  sub: string;
  iss: string;
  email: string;
  display_name: string | null;
  created_at: string;
  last_login: string;
  archived_at: string | null;
  permissions: string[];
}

export interface CurrentUserState {
  currentUser: CurrentUser | null;
  loading: boolean;
}

// Shape of the actual /api/v1/me JSON response.
interface MeApiResponse {
  user: Omit<CurrentUser, 'permissions'>;
  permissions: string[];
}

const CurrentUserContext = createContext<CurrentUserState | undefined>(undefined);

function getApiHeaders(accessToken: string | null): Record<string, string> {
  const headers: Record<string, string> = {};
  if (accessToken) {
    headers['Authorization'] = `Bearer ${accessToken}`;
  }
  return headers;
}

function useLoadCurrentUserState(enabled: boolean = true): CurrentUserState {
  const { accessToken } = useContext(AuthContext);
  const { auth_required } = useContext(AuthConfigContext);
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    if (!enabled) {
      return () => {
        cancelled = true;
      };
    }

    if (auth_required && !accessToken) {
      setCurrentUser(null);
      setLoading(true);
      return () => {
        cancelled = true;
      };
    }

    setLoading(true);

    fetch('/api/v1/me', { headers: getApiHeaders(accessToken) })
      .then((res) => {
        if (!res.ok) throw new Error(`Failed to load current user: ${res.status}`);
        return res.json();
      })
      .then((data: MeApiResponse) => {
        if (!cancelled) {
          setCurrentUser({ ...data.user, permissions: data.permissions });
          setLoading(false);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setCurrentUser(null);
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [enabled, accessToken, auth_required]);

  return { currentUser, loading };
}

export function CurrentUserStateProvider({
  value,
  children
}: {
  value: CurrentUserState;
  children: ReactNode;
}) {
  return createElement(CurrentUserContext.Provider, { value }, children);
}

export function CurrentUserProvider({ children }: { children: ReactNode }) {
  const state = useLoadCurrentUserState();
  return createElement(CurrentUserContext.Provider, { value: state }, children);
}

export function useCurrentUserState(): CurrentUserState {
  const state = useContext(CurrentUserContext);
  const fallbackState = useLoadCurrentUserState(state === undefined);
  return state ?? fallbackState;
}

export function useCurrentUser(): CurrentUser | null {
  const { currentUser } = useCurrentUserState();
  return currentUser;
}
