import { useState, useEffect, useContext } from 'react';
import { AuthContext } from 'src/auth.context';
import { AuthConfigContext } from 'src/authConfig.context';

export interface CurrentUser {
  user_id: string;
  sub: string;
  iss: string;
  email: string;
  display_name: string | null;
  created_at: string;
  last_seen_at: string;
  archived_at: string | null;
}

function getApiHeaders(accessToken: string | null): Record<string, string> {
  const csrfToken =
    document.cookie
      .split('; ')
      .find((row) => row.startsWith('_csrf_token='))
      ?.split('=')[1] ?? '';

  const headers: Record<string, string> = { 'X-CSRFToken': csrfToken };
  if (accessToken) {
    headers['Authorization'] = `Bearer ${accessToken}`;
  }
  return headers;
}

export function useCurrentUser(): CurrentUser | null {
  const { accessToken } = useContext(AuthContext);
  const { auth_required } = useContext(AuthConfigContext);
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);

  useEffect(() => {
    if (auth_required && !accessToken) return;

    fetch('/api/v1/me', { headers: getApiHeaders(accessToken) })
      .then((res) => {
        if (!res.ok) throw new Error(`Failed to load current user: ${res.status}`);
        return res.json();
      })
      .then((data: CurrentUser) => setCurrentUser(data))
      .catch(() => {});
  }, [accessToken, auth_required]);

  return currentUser;
}
