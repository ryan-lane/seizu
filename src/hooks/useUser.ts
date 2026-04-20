import { useState, useEffect, useContext } from 'react';
import { AuthContext } from 'src/auth.context';
import { AuthConfigContext } from 'src/authConfig.context';
import { CurrentUser } from 'src/hooks/useCurrentUser';

function getApiHeaders(accessToken: string | null): Record<string, string> {
  const headers: Record<string, string> = {};
  if (accessToken) {
    headers['Authorization'] = `Bearer ${accessToken}`;
  }
  return headers;
}

export function useUser(userId: string): CurrentUser | null {
  const { accessToken } = useContext(AuthContext);
  const { auth_required } = useContext(AuthConfigContext);
  const [user, setUser] = useState<CurrentUser | null>(null);

  useEffect(() => {
    if (auth_required && !accessToken) return;

    fetch(`/api/v1/users/${encodeURIComponent(userId)}`, {
      headers: getApiHeaders(accessToken),
    })
      .then((res) => {
        if (!res.ok) return null;
        return res.json();
      })
      .then((data: CurrentUser | null) => {
        if (data) setUser(data);
      })
      .catch(() => {});
  }, [userId, accessToken, auth_required]);

  return user;
}
