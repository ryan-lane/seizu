import { useState, useCallback } from 'react';

export type QueryRecord = Record<string, unknown>;

interface QueryState {
  loading: boolean;
  error: Error | null;
  records: QueryRecord[] | undefined;
  first: QueryRecord | undefined;
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
  const [state, setState] = useState<QueryState>({
    loading: false,
    error: null,
    records: undefined,
    first: undefined
  });

  const run = useCallback(
    (params?: Record<string, unknown>) => {
      if (!cypher) return;
      setState({ loading: true, error: null, records: undefined, first: undefined });
      fetch('/api/v1/query', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken()
        },
        body: JSON.stringify({ query: cypher, params })
      })
        .then((res) => res.json())
        .then((data: { error?: string; results?: QueryRecord[] }) => {
          if (data.error) {
            setState({
              loading: false,
              error: new Error(data.error),
              records: undefined,
              first: undefined
            });
          } else {
            const results = data.results || [];
            setState({
              loading: false,
              error: null,
              records: results,
              first: results[0]
            });
          }
        })
        .catch((err: Error) => {
          setState({ loading: false, error: err, records: undefined, first: undefined });
        });
    },
    [cypher]
  );

  return [run, state];
}
