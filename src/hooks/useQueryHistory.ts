import { useState, useCallback, useContext, useRef } from 'react';
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

export function useQueryHistory() {
  const { accessToken } = useContext(AuthContext);
  const { auth_required } = useContext(AuthConfigContext);
  const [state, setState] = useState<HistoryState>({
    loading: false,
    error: null,
    data: null,
  });

  const fetchHistory = useCallback(
    (page: number = 1, perPage: number = 20) => {
      if (auth_required && !accessToken) return;
      setState((s) => ({ ...s, loading: true, error: null }));

      const headers: Record<string, string> = {};
      if (accessToken) {
        headers.Authorization = `Bearer ${accessToken}`;
      }

      fetch(`/api/v1/query-history?page=${page}&per_page=${perPage}`, {
        headers,
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
    [accessToken, auth_required],
  );

  return { ...state, fetchHistory };
}

export function useFetchHistoryItem(): (
  historyId: string,
) => Promise<QueryHistoryItem | null> {
  const { accessToken } = useContext(AuthContext);
  const { auth_required } = useContext(AuthConfigContext);
  const accessTokenRef = useRef(accessToken);
  accessTokenRef.current = accessToken;
  const authRequiredRef = useRef(auth_required);
  authRequiredRef.current = auth_required;

  return useCallback(
    async (historyId: string): Promise<QueryHistoryItem | null> => {
      if (authRequiredRef.current && !accessTokenRef.current) return null;
      const headers: Record<string, string> = {};
      if (accessTokenRef.current)
        headers.Authorization = `Bearer ${accessTokenRef.current}`;
      try {
        const res = await fetch(`/api/v1/query-history/${historyId}`, {
          headers,
        });
        if (!res.ok) return null;
        return res.json() as Promise<QueryHistoryItem>;
      } catch {
        return null;
      }
    },
    [],
  );
}
