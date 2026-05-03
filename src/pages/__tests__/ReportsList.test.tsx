import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import ReportsList from 'src/pages/ReportsList';
import * as reportsApiModule from 'src/hooks/useReportsApi';
import * as permissionsModule from 'src/hooks/usePermissions';

jest.mock('src/hooks/usePermissions', () => ({
  usePermissionState: jest.fn(),
}));

jest.mock('src/components/UserDisplay', () => ({
  __esModule: true,
  default: ({ userId }: { userId: string }) => <>{userId}</>,
}));

const mockUsePermissionState = permissionsModule.usePermissionState as jest.MockedFunction<typeof permissionsModule.usePermissionState>;
const theme = createTheme();

function LocationTracker() {
  const location = useLocation();
  return <div data-testid="location">{`${location.pathname}${location.search}`}</div>;
}

const REPORTS: reportsApiModule.ReportListItem[] = [
  {
    report_id: 'r1',
    name: 'Executive Risk',
    description: '',
    current_version: 3,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-02T00:00:00Z',
    created_by: 'alice',
    updated_by: 'bob',
    access: { scope: 'public' },
    pinned: true,
  },
  {
    report_id: 'r2',
    name: 'Draft Findings',
    description: '',
    current_version: 1,
    created_at: '2026-01-03T00:00:00Z',
    updated_at: '2026-01-04T00:00:00Z',
    created_by: 'carol',
    updated_by: '',
    access: { scope: 'private' },
    pinned: false,
  },
];

function Wrapper({ children }: { children: React.ReactNode }) {
  return (
    <MemoryRouter initialEntries={['/app/reports']}>
      <ThemeProvider theme={theme}>
        <Routes>
          <Route path="/app/reports" element={<>{children}<LocationTracker /></>} />
          <Route path="/app/reports/:reportId" element={<LocationTracker />} />
        </Routes>
      </ThemeProvider>
    </MemoryRouter>
  );
}

describe('ReportsList', () => {
  let mockUseReportsList: jest.Mock;
  let mockUseDashboardReportId: jest.Mock;
  let mockUseReportsMutations: jest.Mock;
  let refreshReports: jest.Mock;
  let cloneReport: jest.Mock;

  beforeEach(() => {
    jest.clearAllMocks();
    mockUseReportsList = jest.spyOn(reportsApiModule, 'useReportsList') as unknown as jest.Mock;
    mockUseDashboardReportId = jest.spyOn(reportsApiModule, 'useDashboardReportId') as unknown as jest.Mock;
    mockUseReportsMutations = jest.spyOn(reportsApiModule, 'useReportsMutations') as unknown as jest.Mock;
    refreshReports = jest.fn();
    cloneReport = jest.fn().mockResolvedValue({
      ...REPORTS[0],
      report_id: 'clone1',
      name: 'Copy of Executive Risk',
    });
    mockUsePermissionState.mockReturnValue({
      hasPermission: (permission: string) => ['reports:write', 'reports:delete', 'reports:set_dashboard'].includes(permission),
      loading: false,
      currentUser: {
        user_id: 'alice',
        sub: 'alice',
        iss: 'test',
        email: 'alice@example.com',
        display_name: 'Alice',
        created_at: '2026-01-01T00:00:00Z',
        last_login: '2026-01-02T00:00:00Z',
        archived_at: null,
        permissions: [],
      },
    });
    mockUseReportsList.mockReturnValue({
      reports: REPORTS,
      total: REPORTS.length,
      page: 1,
      perPage: 500,
      loading: false,
      error: null,
      refresh: refreshReports,
    });
    mockUseDashboardReportId.mockReturnValue({
      dashboardReportId: 'r1',
      loading: false,
      refresh: jest.fn(),
    });
    mockUseReportsMutations.mockReturnValue({
      createReport: jest.fn(),
      cloneReport,
      saveReportVersion: jest.fn(),
      setDashboardReport: jest.fn(),
      pinReport: jest.fn(),
      updateReportVisibility: jest.fn(),
      deleteReport: jest.fn(),
    });
  });

  afterEach(() => {
    cleanup();
    mockUseReportsList.mockRestore?.();
    mockUseDashboardReportId.mockRestore?.();
    mockUseReportsMutations.mockRestore?.();
  });

  it('renders report list columns with visibility and updated-by metadata', () => {
    render(<ReportsList />, { wrapper: Wrapper });

    expect(screen.getByRole('columnheader', { name: 'Visibility' })).toBeInTheDocument();
    expect(screen.getByText('Last updated')).toBeInTheDocument();
    expect(screen.getByText('Updated by')).toBeInTheDocument();

    expect(screen.getByRole('link', { name: 'Executive Risk' })).toBeInTheDocument();
    expect(screen.getByText('Public')).toBeInTheDocument();
    expect(screen.getByText('Pinned')).toBeInTheDocument();
    expect(screen.getByText('Dashboard')).toBeInTheDocument();
    expect(screen.getByText('bob')).toBeInTheDocument();

    expect(screen.getByRole('link', { name: 'Draft Findings' })).toBeInTheDocument();
    expect(screen.getByText('Draft')).toBeInTheDocument();
    expect(screen.getByText('carol')).toBeInTheDocument();
  });

  it('clones from the list view and navigates to the cloned report in edit mode', async () => {
    const user = userEvent.setup();
    render(<ReportsList />, { wrapper: Wrapper });

    await user.click(screen.getAllByLabelText('More actions')[0]);
    await user.click(screen.getByRole('menuitem', { name: /clone/i }));

    expect(screen.getByRole('textbox', { name: 'New report name' })).toHaveValue('Copy of Executive Risk');

    await user.click(screen.getByRole('button', { name: 'Clone' }));

    await waitFor(() => {
      expect(cloneReport).toHaveBeenCalledWith('r1', 'Copy of Executive Risk');
    });
    expect(refreshReports).toHaveBeenCalledTimes(1);
    await waitFor(() => {
      expect(screen.getByTestId('location')).toHaveTextContent('/app/reports/clone1?edit=true');
    });
  });
});
