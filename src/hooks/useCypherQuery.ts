import { useState, useCallback, useContext } from 'react';
import { AuthContext } from 'src/auth.context';
import { AuthConfigContext } from 'src/authConfig.context';

export type QueryRecord = Record<string, unknown>;

interface QueryState {
  loading: boolean;
  error: Error | null;
  records: QueryRecord[] | undefined;
  first: QueryRecord | undefined;
  warnings: string[];
  queryErrors: string[];
}

function getCsrfToken(): string {
  return (
    document.cookie
      .split('; ')
      .find((row) => row.startsWith('_csrf_token='))
      ?.split('=')[1] || ''
  );
}

export function useLazyCypherQuery(
  cypher?: string
): [(params?: Record<string, unknown>) => void, QueryState] {
  const { accessToken } = useContext(AuthContext);
  const { auth_required } = useContext(AuthConfigContext);
  const [state, setState] = useState<QueryState>({
    loading: false,
    error: null,
    records: undefined,
    first: undefined,
    warnings: [],
    queryErrors: []
  });

  const run = useCallback(
    (params?: Record<string, unknown>) => {
      if (!cypher) return;
      // When auth is required, wait until we have a token before querying.
      if (auth_required && !accessToken) return;
      setState({ loading: true, error: null, records: undefined, first: undefined, warnings: [], queryErrors: [] });

      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrfToken()
      };
      if (accessToken) {
        headers['Authorization'] = `Bearer ${accessToken}`;
      }

      fetch('/api/v1/query', {
        method: 'POST',
        headers,
        body: JSON.stringify({ query: cypher, params })
      })
        .then((res) => res.json())
        .then((data: { error?: string; errors?: string[]; warnings?: string[]; results?: QueryRecord[] }) => {
          const validationErrors = data.errors ?? [];
          const validationWarnings = data.warnings ?? [];

          if (data.error) {
            // Server or request-level error (HTTP 500, malformed request, etc.)
            setState({
              loading: false,
              error: new Error(data.error),
              records: undefined,
              first: undefined,
              warnings: [],
              queryErrors: []
            });
          } else if (validationErrors.length > 0) {
            // Query validation errors — query was not executed
            setState({
              loading: false,
              error: null,
              records: undefined,
              first: undefined,
              warnings: validationWarnings,
              queryErrors: validationErrors
            });
          } else {
            const results = data.results ?? [];
            setState({
              loading: false,
              error: null,
              records: results,
              first: results[0],
              warnings: validationWarnings,
              queryErrors: []
            });
          }
        })
        .catch((err: Error) => {
          setState({ loading: false, error: err, records: undefined, first: undefined, warnings: [], queryErrors: [] });
        });
    },
    [cypher, accessToken, auth_required]
  );

  return [run, state];
}
