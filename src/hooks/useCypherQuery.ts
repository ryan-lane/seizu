import { useState, useCallback, useContext } from 'react';
import { AuthContext } from 'src/auth.context';
import { AuthConfigContext } from 'src/authConfig.context';
import { usePermissionState } from 'src/hooks/usePermissions';

export type QueryRecord = Record<string, unknown>;

export interface QueryState {
  loading: boolean;
  error: Error | null;
  records: QueryRecord[] | undefined;
  first: QueryRecord | undefined;
  warnings: string[];
  queryErrors: string[];
  tokenExpired: boolean;
}

export function useLazyCypherQuery(
  cypher?: string,
  reportToken?: string
): [(params?: Record<string, unknown>) => void, QueryState] {
  const { accessToken } = useContext(AuthContext);
  const { auth_required } = useContext(AuthConfigContext);
  const { hasPermission, loading: permissionsLoading } = usePermissionState();
  const [state, setState] = useState<QueryState>({
    loading: false,
    error: null,
    records: undefined,
    first: undefined,
    warnings: [],
    queryErrors: [],
    tokenExpired: false,
  });

  const run = useCallback(
    (params?: Record<string, unknown>) => {
      if (!cypher) return;
      // When auth is required, wait until we have a token before querying.
      if (auth_required && !accessToken) return;
      if (permissionsLoading) return;

      const requiredPermission = reportToken ? 'reports:read' : 'query:execute';
      if (!hasPermission(requiredPermission)) {
        setState({
          loading: false,
          error: new Error('You do not have permission to run this query.'),
          records: undefined,
          first: undefined,
          warnings: [],
          queryErrors: [],
          tokenExpired: false,
        });
        return;
      }

      setState({ loading: true, error: null, records: undefined, first: undefined, warnings: [], queryErrors: [], tokenExpired: false });

      const headers: Record<string, string> = {
        'Content-Type': 'application/json'
      };
      if (accessToken) {
        headers['Authorization'] = `Bearer ${accessToken}`;
      }

      const endpoint = reportToken ? '/api/v1/query/report' : '/api/v1/query/adhoc';
      const body = reportToken
        ? { token: reportToken, params }
        : { query: cypher, params };

      fetch(endpoint, {
        method: 'POST',
        headers,
        body: JSON.stringify(body)
      })
        .then((res) => res.json())
        .then((data: { error?: string; code?: string; errors?: string[]; warnings?: string[]; results?: QueryRecord[] }) => {
          const validationErrors = data.errors ?? [];
          const validationWarnings = data.warnings ?? [];

          if (data.error) {
            if (data.code === 'token_expired') {
              // Keep records/first from previous state so panels continue showing stale data
              // while the token refresh and retry are in flight.
              setState((prev) => ({
                ...prev,
                loading: false,
                error: null,
                tokenExpired: true,
              }));
            } else {
              // Server or request-level error (HTTP 500, malformed request, etc.)
              setState({
                loading: false,
                error: new Error(data.error),
                records: undefined,
                first: undefined,
                warnings: [],
                queryErrors: [],
                tokenExpired: false,
              });
            }
          } else if (validationErrors.length > 0) {
            // Query validation errors — query was not executed
            setState({
              loading: false,
              error: null,
              records: undefined,
              first: undefined,
              warnings: validationWarnings,
              queryErrors: validationErrors,
              tokenExpired: false,
            });
          } else {
            const results = data.results ?? [];
            setState({
              loading: false,
              error: null,
              records: results,
              first: results[0],
              warnings: validationWarnings,
              queryErrors: [],
              tokenExpired: false,
            });
          }
        })
        .catch((err: Error) => {
          setState({ loading: false, error: err, records: undefined, first: undefined, warnings: [], queryErrors: [], tokenExpired: false });
        });
    },
    [cypher, reportToken, accessToken, auth_required, permissionsLoading, hasPermission]
  );

  return [run, state];
}
