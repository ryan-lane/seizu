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
  last_login: string;
  archived_at: string | null;
  permissions: string[];
}

// Shape of the actual /api/v1/me JSON response.
interface MeApiResponse {
  user: Omit<CurrentUser, 'permissions'>;
  permissions: string[];
}

function getApiHeaders(accessToken: string | null): Record<string, string> {
  const headers: Record<string, string> = {};
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
      .then((data: MeApiResponse) => setCurrentUser({ ...data.user, permissions: data.permissions }))
      .catch(() => {});
  }, [accessToken, auth_required]);

  return currentUser;
}
