import { useState, useEffect, useContext, useCallback } from 'react';
import { AuthContext } from 'src/auth.context';
import { AuthConfigContext } from 'src/authConfig.context';
import { Report } from 'src/config.context';

export interface ReportListItem {
  report_id: string;
  name: string;
  description: string;
  current_version: number;
  created_at: string;
  updated_at: string;
  pinned: boolean;
}

export interface ReportVersion {
  report_id: string;
  name: string;
  version: number;
  config: Report;
  created_at: string;
  created_by: string;
  comment: string | null;
  query_capabilities?: Record<string, string>;
}

function getApiHeaders(accessToken: string | null): Record<string, string> {
  const headers: Record<string, string> = {};
  if (accessToken) {
    headers['Authorization'] = `Bearer ${accessToken}`;
  }
  return headers;
}

const REPORTS_UPDATED = 'seizu:reports-updated';

function broadcastReportsUpdated() {
  window.dispatchEvent(new Event(REPORTS_UPDATED));
}

export function useReportsList(): {
  reports: ReportListItem[];
  loading: boolean;
  error: Error | null;
  refresh: () => void;
} {
  const { accessToken } = useContext(AuthContext);
  const { auth_required } = useContext(AuthConfigContext);
  const [reports, setReports] = useState<ReportListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    const handler = () => setTick((t) => t + 1);
    window.addEventListener(REPORTS_UPDATED, handler);
    return () => window.removeEventListener(REPORTS_UPDATED, handler);
  }, []);

  const refresh = useCallback(() => broadcastReportsUpdated(), []);

  useEffect(() => {
    if (auth_required && !accessToken) return;

    setLoading(true);
    fetch('/api/v1/reports', { headers: getApiHeaders(accessToken) })
      .then((res) => {
        if (!res.ok) throw new Error(`Failed to load reports list: ${res.status}`);
        return res.json();
      })
      .then((data: { reports: ReportListItem[] }) => {
        setReports(data.reports ?? []);
        setLoading(false);
      })
      .catch((err: Error) => {
        setError(err);
        setLoading(false);
      });
  }, [accessToken, auth_required, tick]);

  return { reports, loading, error, refresh };
}

export function useDashboardReportId(): {
  dashboardReportId: string | null;
  loading: boolean;
  refresh: () => void;
} {
  const { accessToken } = useContext(AuthContext);
  const { auth_required } = useContext(AuthConfigContext);
  const [dashboardReportId, setDashboardReportId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [tick, setTick] = useState(0);

  const refresh = useCallback(() => setTick((t) => t + 1), []);

  useEffect(() => {
    if (auth_required && !accessToken) return;

    setLoading(true);
    fetch('/api/v1/reports/dashboard', { headers: getApiHeaders(accessToken) })
      .then((res) => {
        if (res.status === 404) {
          setDashboardReportId(null);
          setLoading(false);
          return null;
        }
        if (!res.ok) throw new Error(`Failed to load dashboard: ${res.status}`);
        return res.json();
      })
      .then((data: ReportVersion | null) => {
        setDashboardReportId(data?.report_id ?? null);
        setLoading(false);
      })
      .catch(() => {
        setDashboardReportId(null);
        setLoading(false);
      });
  }, [accessToken, auth_required, tick]);

  return { dashboardReportId, loading, refresh };
}

export function useDashboardReport(): {
  report: Report | undefined;
  queryCapabilities: Record<string, string> | undefined;
  loading: boolean;
  notConfigured: boolean;
} {
  const { accessToken } = useContext(AuthContext);
  const { auth_required } = useContext(AuthConfigContext);
  const [report, setReport] = useState<Report | undefined>(undefined);
  const [queryCapabilities, setQueryCapabilities] = useState<Record<string, string> | undefined>(undefined);
  const [loading, setLoading] = useState(true);
  const [notConfigured, setNotConfigured] = useState(false);

  useEffect(() => {
    if (auth_required && !accessToken) return;

    setLoading(true);
    setReport(undefined);
    setQueryCapabilities(undefined);
    setNotConfigured(false);

    fetch('/api/v1/reports/dashboard', { headers: getApiHeaders(accessToken) })
      .then((res) => {
        if (res.status === 404) {
          setNotConfigured(true);
          setLoading(false);
          return null;
        }
        if (!res.ok) throw new Error(`Failed to load dashboard report: ${res.status}`);
        return res.json();
      })
      .then((data: ReportVersion | null) => {
        if (data) {
          setReport(data.config);
          setQueryCapabilities(data.query_capabilities);
        }
        setLoading(false);
      })
      .catch(() => {
        setNotConfigured(true);
        setLoading(false);
      });
  }, [accessToken, auth_required]);

  return { report, queryCapabilities, loading, notConfigured };
}

export function useAllReports(): {
  reports: Report[];
  loading: boolean;
} {
  const { accessToken } = useContext(AuthContext);
  const { auth_required } = useContext(AuthConfigContext);
  const [reports, setReports] = useState<Report[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (auth_required && !accessToken) return;

    setLoading(true);

    fetch('/api/v1/reports', { headers: getApiHeaders(accessToken) })
      .then((res) => {
        if (!res.ok) throw new Error(`Failed to load reports list: ${res.status}`);
        return res.json();
      })
      .then((data: { reports: ReportListItem[] }) => {
        const items = data.reports ?? [];
        return Promise.all(
          items.map((item) =>
            fetch(`/api/v1/reports/${item.report_id}`, {
              headers: getApiHeaders(accessToken)
            })
              .then((res) => res.json())
              .then((v: ReportVersion) => v.config)
          )
        );
      })
      .then((allReports: Report[]) => {
        setReports(allReports);
        setLoading(false);
      })
      .catch(() => {
        setLoading(false);
      });
  }, [accessToken, auth_required]);

  return { reports, loading };
}

export function useReportsMutations(): {
  createReport: (name: string) => Promise<ReportListItem>;
  saveReportVersion: (
    reportId: string,
    config: Report,
    comment?: string
  ) => Promise<ReportVersion>;
  setDashboardReport: (reportId: string) => Promise<void>;
  pinReport: (reportId: string, pinned: boolean) => Promise<void>;
  deleteReport: (reportId: string) => Promise<void>;
} {
  const { accessToken } = useContext(AuthContext);

  const createReport = useCallback(
    async (name: string): Promise<ReportListItem> => {
      const res = await fetch('/api/v1/reports', {
        method: 'POST',
        headers: {
          ...getApiHeaders(accessToken),
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ name })
      });
      if (!res.ok) throw new Error(`Failed to create report: ${res.status}`);
      return res.json();
    },
    [accessToken]
  );

  const saveReportVersion = useCallback(
    async (reportId: string, config: Report, comment?: string): Promise<ReportVersion> => {
      const res = await fetch(`/api/v1/reports/${reportId}/versions`, {
        method: 'POST',
        headers: {
          ...getApiHeaders(accessToken),
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ config, comment: comment ?? null })
      });
      if (!res.ok) throw new Error(`Failed to save report version: ${res.status}`);
      return res.json();
    },
    [accessToken]
  );

  const setDashboardReport = useCallback(
    async (reportId: string): Promise<void> => {
      const res = await fetch(`/api/v1/reports/${reportId}/dashboard`, {
        method: 'PUT',
        headers: getApiHeaders(accessToken)
      });
      if (!res.ok) throw new Error(`Failed to set dashboard: ${res.status}`);
    },
    [accessToken]
  );

  const pinReport = useCallback(
    async (reportId: string, pinned: boolean): Promise<void> => {
      const res = await fetch(`/api/v1/reports/${reportId}/pin`, {
        method: 'PUT',
        headers: {
          ...getApiHeaders(accessToken),
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ pinned })
      });
      if (!res.ok) throw new Error(`Failed to update pin: ${res.status}`);
    },
    [accessToken]
  );

  const deleteReport = useCallback(
    async (reportId: string): Promise<void> => {
      const res = await fetch(`/api/v1/reports/${reportId}`, {
        method: 'DELETE',
        headers: getApiHeaders(accessToken)
      });
      if (!res.ok) throw new Error(`Failed to delete report: ${res.status}`);
    },
    [accessToken]
  );

  return { createReport, saveReportVersion, setDashboardReport, pinReport, deleteReport };
}

export function useReportVersionsList(reportId: string | undefined): {
  versions: ReportVersion[];
  loading: boolean;
  error: Error | null;
} {
  const { accessToken } = useContext(AuthContext);
  const { auth_required } = useContext(AuthConfigContext);
  const [versions, setVersions] = useState<ReportVersion[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    if (!reportId) return;
    if (auth_required && !accessToken) return;

    setLoading(true);
    fetch(`/api/v1/reports/${reportId}/versions`, { headers: getApiHeaders(accessToken) })
      .then((res) => {
        if (!res.ok) throw new Error(`Failed to load versions: ${res.status}`);
        return res.json();
      })
      .then((data: { versions: ReportVersion[] }) => {
        setVersions(data.versions ?? []);
        setLoading(false);
      })
      .catch((err: Error) => {
        setError(err);
        setLoading(false);
      });
  }, [reportId, accessToken, auth_required]);

  return { versions, loading, error };
}

export function useReportVersion(
  reportId: string | undefined,
  versionNum: string | undefined
): {
  reportVersion: ReportVersion | undefined;
  loading: boolean;
  error: Error | null;
} {
  const { accessToken } = useContext(AuthContext);
  const { auth_required } = useContext(AuthConfigContext);
  const [reportVersion, setReportVersion] = useState<ReportVersion | undefined>(undefined);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    if (!reportId || !versionNum) return;
    if (auth_required && !accessToken) return;

    setLoading(true);
    setReportVersion(undefined);
    setError(null);

    fetch(`/api/v1/reports/${reportId}/versions/${versionNum}`, {
      headers: getApiHeaders(accessToken)
    })
      .then((res) => {
        if (!res.ok) throw new Error(`Failed to load version: ${res.status}`);
        return res.json();
      })
      .then((data: ReportVersion) => {
        setReportVersion(data);
        setLoading(false);
      })
      .catch((err: Error) => {
        setError(err);
        setLoading(false);
      });
  }, [reportId, versionNum, accessToken, auth_required]);

  return { reportVersion, loading, error };
}

export function useReport(reportId: string | undefined): {
  report: Report | undefined;
  name: string | undefined;
  queryCapabilities: Record<string, string> | undefined;
  loading: boolean;
  error: Error | null;
} {
  const { accessToken } = useContext(AuthContext);
  const { auth_required } = useContext(AuthConfigContext);
  const [report, setReport] = useState<Report | undefined>(undefined);
  const [name, setName] = useState<string | undefined>(undefined);
  const [queryCapabilities, setQueryCapabilities] = useState<Record<string, string> | undefined>(undefined);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    if (!reportId) return;
    if (auth_required && !accessToken) return;

    setLoading(true);
    setReport(undefined);
    setName(undefined);
    setQueryCapabilities(undefined);
    setError(null);

    fetch(`/api/v1/reports/${reportId}`, { headers: getApiHeaders(accessToken) })
      .then((res) => {
        if (!res.ok) throw new Error(`Failed to load report: ${res.status}`);
        return res.json();
      })
      .then((data: ReportVersion) => {
        setReport(data.config);
        setName(data.name);
        setQueryCapabilities(data.query_capabilities);
        setLoading(false);
      })
      .catch((err: Error) => {
        setError(err);
        setLoading(false);
      });
  }, [reportId, accessToken, auth_required]);

  return { report, name, queryCapabilities, loading, error };
}
