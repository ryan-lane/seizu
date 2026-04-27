import { act, renderHook, waitFor } from '@testing-library/react';
import { AuthContext } from 'src/auth.context';
import { AuthConfigContext } from 'src/authConfig.context';
import { useReportVersionsList, useReportVersion, useReportsList, useReportsMutations } from 'src/hooks/useReportsApi';

const AUTH_CONFIG_NO_OIDC = { auth_required: false, oidc: null, userManager: null };

function makeWrapper(authRequired: boolean, accessToken: string | null) {
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <AuthConfigContext.Provider value={{ ...AUTH_CONFIG_NO_OIDC, auth_required: authRequired }}>
        <AuthContext.Provider value={{ user: null, accessToken, isLoading: false }}>
          {children}
        </AuthContext.Provider>
      </AuthConfigContext.Provider>
    );
  };
}

const VERSIONS = [
  {
    report_id: 'r1',
    name: 'My Report',
    version: 1,
    config: { rows: [] },
    created_at: '2024-01-01T00:00:00Z',
    created_by: 'alice@example.com',
    comment: 'Initial version'
  },
  {
    report_id: 'r1',
    name: 'My Report',
    version: 2,
    config: { rows: [] },
    created_at: '2024-01-02T00:00:00Z',
    created_by: 'bob@example.com',
    comment: null
  }
];

// ---------------------------------------------------------------------------
// useReportVersionsList
// ---------------------------------------------------------------------------

describe('useReportVersionsList', () => {
  let mockFetch: jest.Mock;

  beforeEach(() => {
    jest.clearAllMocks();
    mockFetch = jest.fn();
    global.fetch = mockFetch;
  });

  it('fetches versions for a report', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ versions: VERSIONS })
    });

    const { result } = renderHook(() => useReportVersionsList('r1'), {
      wrapper: makeWrapper(false, null)
    });

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.versions).toEqual(VERSIONS);
    expect(result.current.error).toBeNull();
    expect(mockFetch).toHaveBeenCalledWith(
      '/api/v1/reports/r1/versions',
      expect.any(Object)
    );
  });

  it('does not fetch when auth_required and accessToken is null', () => {
    renderHook(() => useReportVersionsList('r1'), {
      wrapper: makeWrapper(true, null)
    });

    expect(mockFetch).not.toHaveBeenCalled();
  });

  it('does not fetch when reportId is undefined', () => {
    renderHook(() => useReportVersionsList(undefined), {
      wrapper: makeWrapper(false, null)
    });

    expect(mockFetch).not.toHaveBeenCalled();
  });

  it('includes Authorization header when accessToken is set', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ versions: VERSIONS })
    });

    renderHook(() => useReportVersionsList('r1'), {
      wrapper: makeWrapper(true, 'mytoken')
    });

    await waitFor(() => expect(mockFetch).toHaveBeenCalled());
    expect(mockFetch).toHaveBeenCalledWith(
      '/api/v1/reports/r1/versions',
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: 'Bearer mytoken' })
      })
    );
  });

  it('sets error when fetch returns non-ok status', async () => {
    mockFetch.mockResolvedValue({ ok: false, status: 500 });

    const { result } = renderHook(() => useReportVersionsList('r1'), {
      wrapper: makeWrapper(false, null)
    });

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error).not.toBeNull();
    expect(result.current.versions).toEqual([]);
  });

  it('sets error when fetch rejects', async () => {
    mockFetch.mockRejectedValue(new Error('network error'));

    const { result } = renderHook(() => useReportVersionsList('r1'), {
      wrapper: makeWrapper(false, null)
    });

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error).not.toBeNull();
  });
});

// ---------------------------------------------------------------------------
// useReportVersion
// ---------------------------------------------------------------------------

describe('useReportVersion', () => {
  let mockFetch: jest.Mock;

  beforeEach(() => {
    jest.clearAllMocks();
    mockFetch = jest.fn();
    global.fetch = mockFetch;
  });

  it('fetches a specific version', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(VERSIONS[0])
    });

    const { result } = renderHook(() => useReportVersion('r1', '1'), {
      wrapper: makeWrapper(false, null)
    });

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.reportVersion).toEqual(VERSIONS[0]);
    expect(result.current.error).toBeNull();
    expect(mockFetch).toHaveBeenCalledWith(
      '/api/v1/reports/r1/versions/1?include_query_capabilities=true',
      expect.any(Object)
    );
  });

  it('does not fetch when auth_required and accessToken is null', () => {
    renderHook(() => useReportVersion('r1', '1'), {
      wrapper: makeWrapper(true, null)
    });

    expect(mockFetch).not.toHaveBeenCalled();
  });

  it('does not fetch when reportId is undefined', () => {
    renderHook(() => useReportVersion(undefined, '1'), {
      wrapper: makeWrapper(false, null)
    });

    expect(mockFetch).not.toHaveBeenCalled();
  });

  it('does not fetch when versionNum is undefined', () => {
    renderHook(() => useReportVersion('r1', undefined), {
      wrapper: makeWrapper(false, null)
    });

    expect(mockFetch).not.toHaveBeenCalled();
  });

  it('includes Authorization header when accessToken is set', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(VERSIONS[1])
    });

    renderHook(() => useReportVersion('r1', '2'), {
      wrapper: makeWrapper(true, 'mytoken')
    });

    await waitFor(() => expect(mockFetch).toHaveBeenCalled());
    expect(mockFetch).toHaveBeenCalledWith(
      '/api/v1/reports/r1/versions/2?include_query_capabilities=true',
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: 'Bearer mytoken' })
      })
    );
  });

  it('sets error when fetch returns non-ok status', async () => {
    mockFetch.mockResolvedValue({ ok: false, status: 404 });

    const { result } = renderHook(() => useReportVersion('r1', '99'), {
      wrapper: makeWrapper(false, null)
    });

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error).not.toBeNull();
    expect(result.current.reportVersion).toBeUndefined();
  });

  it('resets reportVersion when reportId changes', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(VERSIONS[0])
    });

    const { result, rerender } = renderHook(
      ({ id, ver }: { id: string; ver: string }) => useReportVersion(id, ver),
      {
        initialProps: { id: 'r1', ver: '1' },
        wrapper: makeWrapper(false, null)
      }
    );

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.reportVersion).toEqual(VERSIONS[0]);

    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(VERSIONS[1])
    });

    rerender({ id: 'r2', ver: '1' });

    // Wait for new data to load after the reportId change
    await waitFor(() => expect(result.current.reportVersion).toEqual(VERSIONS[1]));
    expect(result.current.loading).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// useReportsList
// ---------------------------------------------------------------------------

const REPORTS = [
  {
    report_id: 'r1',
    name: 'Alpha',
    description: '',
    current_version: 2,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-02T00:00:00Z',
    pinned: false
  },
  {
    report_id: 'r2',
    name: 'Beta',
    description: '',
    current_version: 1,
    created_at: '2024-01-03T00:00:00Z',
    updated_at: '2024-01-03T00:00:00Z',
    pinned: true
  }
];

describe('useReportsList', () => {
  let mockFetch: jest.Mock;

  beforeEach(() => {
    jest.clearAllMocks();
    mockFetch = jest.fn();
    global.fetch = mockFetch;
  });

  it('fetches and returns reports list', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ reports: REPORTS })
    });

    const { result } = renderHook(() => useReportsList(), {
      wrapper: makeWrapper(false, null)
    });

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.reports).toEqual(REPORTS);
    expect(result.current.error).toBeNull();
  });

  it('includes pinned field in returned items', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ reports: REPORTS })
    });

    const { result } = renderHook(() => useReportsList(), {
      wrapper: makeWrapper(false, null)
    });

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.reports[1].pinned).toBe(true);
    expect(result.current.reports[0].pinned).toBe(false);
  });

  it('does not fetch when auth_required and no token', () => {
    renderHook(() => useReportsList(), {
      wrapper: makeWrapper(true, null)
    });

    expect(mockFetch).not.toHaveBeenCalled();
  });

  it('refresh dispatches the seizu:reports-updated event', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ reports: REPORTS })
    });

    const { result } = renderHook(() => useReportsList(), {
      wrapper: makeWrapper(false, null)
    });

    await waitFor(() => expect(result.current.loading).toBe(false));

    const handler = jest.fn();
    window.addEventListener('seizu:reports-updated', handler);
    result.current.refresh();
    expect(handler).toHaveBeenCalledTimes(1);
    window.removeEventListener('seizu:reports-updated', handler);
  });


  it('sets error state on non-ok response', async () => {
    mockFetch.mockResolvedValue({ ok: false, status: 500 });

    const { result } = renderHook(() => useReportsList(), {
      wrapper: makeWrapper(false, null)
    });

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error).not.toBeNull();
    expect(result.current.reports).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// useReportsMutations – pinReport
// ---------------------------------------------------------------------------

describe('useReportsMutations (pinReport)', () => {
  let mockFetch: jest.Mock;

  beforeEach(() => {
    jest.clearAllMocks();
    mockFetch = jest.fn();
    global.fetch = mockFetch;
  });

  it('pinReport calls PUT /api/v1/reports/:id/pin with pinned true', async () => {
    mockFetch.mockResolvedValue({ ok: true });

    const { result } = renderHook(() => useReportsMutations(), {
      wrapper: makeWrapper(false, null)
    });


    await act(async () => {
      await result.current.pinReport('r1', true);
    });

    expect(mockFetch).toHaveBeenCalledWith(
      '/api/v1/reports/r1/pin',
      expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify({ pinned: true })
      })
    );
  });

  it('pinReport calls PUT /api/v1/reports/:id/pin with pinned false', async () => {
    mockFetch.mockResolvedValue({ ok: true });

    const { result } = renderHook(() => useReportsMutations(), {
      wrapper: makeWrapper(false, null)
    });


    await act(async () => {
      await result.current.pinReport('r1', false);
    });

    expect(mockFetch).toHaveBeenCalledWith(
      '/api/v1/reports/r1/pin',
      expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify({ pinned: false })
      })
    );
  });

  it('pinReport throws on non-ok response', async () => {
    mockFetch.mockResolvedValue({ ok: false, status: 403 });

    const { result } = renderHook(() => useReportsMutations(), {
      wrapper: makeWrapper(false, null)
    });


    await act(async () => {
      await expect(result.current.pinReport('r1', true)).rejects.toThrow();
    });
  });
});
