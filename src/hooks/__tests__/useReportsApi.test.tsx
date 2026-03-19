import { renderHook, waitFor } from '@testing-library/react';
import { AuthContext } from 'src/auth.context';
import { AuthConfigContext } from 'src/authConfig.context';
import { useReportVersionsList, useReportVersion } from 'src/hooks/useReportsApi';

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
  beforeEach(() => {
    jest.clearAllMocks();
    Object.defineProperty(document, 'cookie', {
      writable: true,
      value: '_csrf_token=testtoken'
    });
  });

  it('fetches versions for a report', async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ versions: VERSIONS })
    });

    const { result } = renderHook(() => useReportVersionsList('r1'), {
      wrapper: makeWrapper(false, null)
    });

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.versions).toEqual(VERSIONS);
    expect(result.current.error).toBeNull();
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/v1/reports/r1/versions',
      expect.any(Object)
    );
  });

  it('does not fetch when auth_required and accessToken is null', () => {
    global.fetch = jest.fn();

    renderHook(() => useReportVersionsList('r1'), {
      wrapper: makeWrapper(true, null)
    });

    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('does not fetch when reportId is undefined', () => {
    global.fetch = jest.fn();

    renderHook(() => useReportVersionsList(undefined), {
      wrapper: makeWrapper(false, null)
    });

    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('includes Authorization header when accessToken is set', async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ versions: VERSIONS })
    });

    renderHook(() => useReportVersionsList('r1'), {
      wrapper: makeWrapper(true, 'mytoken')
    });

    await waitFor(() => expect(global.fetch).toHaveBeenCalled());
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/v1/reports/r1/versions',
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: 'Bearer mytoken' })
      })
    );
  });

  it('sets error when fetch returns non-ok status', async () => {
    global.fetch = jest.fn().mockResolvedValue({ ok: false, status: 500 });

    const { result } = renderHook(() => useReportVersionsList('r1'), {
      wrapper: makeWrapper(false, null)
    });

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error).not.toBeNull();
    expect(result.current.versions).toEqual([]);
  });

  it('sets error when fetch rejects', async () => {
    global.fetch = jest.fn().mockRejectedValue(new Error('network error'));

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
  beforeEach(() => {
    jest.clearAllMocks();
    Object.defineProperty(document, 'cookie', {
      writable: true,
      value: '_csrf_token=testtoken'
    });
  });

  it('fetches a specific version', async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(VERSIONS[0])
    });

    const { result } = renderHook(() => useReportVersion('r1', '1'), {
      wrapper: makeWrapper(false, null)
    });

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.reportVersion).toEqual(VERSIONS[0]);
    expect(result.current.error).toBeNull();
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/v1/reports/r1/versions/1',
      expect.any(Object)
    );
  });

  it('does not fetch when auth_required and accessToken is null', () => {
    global.fetch = jest.fn();

    renderHook(() => useReportVersion('r1', '1'), {
      wrapper: makeWrapper(true, null)
    });

    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('does not fetch when reportId is undefined', () => {
    global.fetch = jest.fn();

    renderHook(() => useReportVersion(undefined, '1'), {
      wrapper: makeWrapper(false, null)
    });

    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('does not fetch when versionNum is undefined', () => {
    global.fetch = jest.fn();

    renderHook(() => useReportVersion('r1', undefined), {
      wrapper: makeWrapper(false, null)
    });

    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('includes Authorization header when accessToken is set', async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(VERSIONS[1])
    });

    renderHook(() => useReportVersion('r1', '2'), {
      wrapper: makeWrapper(true, 'mytoken')
    });

    await waitFor(() => expect(global.fetch).toHaveBeenCalled());
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/v1/reports/r1/versions/2',
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: 'Bearer mytoken' })
      })
    );
  });

  it('sets error when fetch returns non-ok status', async () => {
    global.fetch = jest.fn().mockResolvedValue({ ok: false, status: 404 });

    const { result } = renderHook(() => useReportVersion('r1', '99'), {
      wrapper: makeWrapper(false, null)
    });

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error).not.toBeNull();
    expect(result.current.reportVersion).toBeUndefined();
  });

  it('resets reportVersion when reportId changes', async () => {
    global.fetch = jest.fn().mockResolvedValue({
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

    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(VERSIONS[1])
    });

    rerender({ id: 'r2', ver: '1' });

    // Should reset to undefined while re-fetching
    expect(result.current.reportVersion).toBeUndefined();

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.reportVersion).toEqual(VERSIONS[1]);
  });
});
