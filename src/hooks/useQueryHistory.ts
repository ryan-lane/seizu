import { useState, useCallback, useContext } from 'react';
import { AuthContext } from 'src/auth.context';
import { AuthConfigContext } from 'src/authConfig.context';

export interface QueryHistoryItem {
  history_id: string;
  user_id: string;
  query: string;
  executed_at: string;
}

export interface QueryHistoryPage {
  items: QueryHistoryItem[];
  total: number;
  page: number;
  per_page: number;
}

interface HistoryState {
  loading: boolean;
  error: Error | null;
  data: QueryHistoryPage | null;
}

function getCsrfToken(): string {
  return (
    document.cookie
      .split('; ')
      .find((row) => row.startsWith('_csrf_token='))
      ?.split('=')[1] || ''
  );
}

export function useQueryHistory() {
  const { accessToken } = useContext(AuthContext);
  const { auth_required } = useContext(AuthConfigContext);
  const [state, setState] = useState<HistoryState>({
    loading: false,
    error: null,
    data: null
  });

  const fetchHistory = useCallback(
    (page: number = 1, perPage: number = 20) => {
      if (auth_required && !accessToken) return;
      setState((s) => ({ ...s, loading: true, error: null }));

      const headers: Record<string, string> = {
        'X-CSRFToken': getCsrfToken()
      };
      if (accessToken) {
        headers.Authorization = `Bearer ${accessToken}`;
      }

      fetch(`/api/v1/query-history?page=${page}&per_page=${perPage}`, {
        headers
      })
        .then((res) => {
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          return res.json();
        })
        .then((data: QueryHistoryPage) => {
          setState({ loading: false, error: null, data });
        })
        .catch((err: Error) => {
          setState({ loading: false, error: err, data: null });
        });
    },
    [accessToken, auth_required]
  );

  return { ...state, fetchHistory };
}
