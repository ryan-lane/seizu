import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';
import { MemoryRouter, Routes, Route, useLocation } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import ReportVersionView from 'src/pages/ReportVersionView';
import * as reportsApiModule from 'src/hooks/useReportsApi';
import * as usePermissionsModule from 'src/hooks/usePermissions';

jest.mock('src/hooks/usePermissions', () => ({
  usePermissions: jest.fn(),
}));

const mockUsePermissions = usePermissionsModule.usePermissions as jest.MockedFunction<typeof usePermissionsModule.usePermissions>;

jest.mock('react-helmet', () => ({
  Helmet: ({ children }: { children: React.ReactNode }) => <>{children}</>
}));

// Prevent ReportView's panel sub-components from making real HTTP calls.
// Do NOT mock src/components/ReportView itself — that leaks into ReportView.test.tsx
// which tests ReportView directly (Bun shares the module registry across files).
// The test reports use { rows: [] } so no panels (and no fetch calls) are rendered.
//
// useReportsApi is mocked via jest.spyOn so the spy can be restored with
// jest.restoreAllMocks() in afterAll, preventing the mock from leaking into
// useReportsApi.test.tsx when test files run in an order where this file executes first.

const theme = createTheme();

// Tracks the current location so tests can observe navigate() calls.
function TestLocation() {
  const { pathname } = useLocation();
  return <div data-testid="nav-location" style={{ display: 'none' }}>{pathname}</div>;
}

function makeWrapper(initialPath: string = '/app/reports/r1/versions/1') {
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <MemoryRouter initialEntries={[initialPath]}>
        <ThemeProvider theme={theme}>
          <TestLocation />
          <Routes>
            <Route path="/app/reports/:id/versions/:version" element={<>{children}</>} />
          </Routes>
        </ThemeProvider>
      </MemoryRouter>
    );
  };
}

const Wrapper = makeWrapper();

const VERSION_1 = {
  report_id: 'r1',
  name: 'My Report',
  version: 1,
  config: { rows: [] },
  created_at: '2024-01-01T00:00:00Z',
  created_by: 'alice@example.com',
  comment: 'Initial version'
};

const VERSION_2 = {
  report_id: 'r1',
  name: 'My Report',
  version: 2,
  config: { rows: [] },
  created_at: '2024-01-02T00:00:00Z',
  created_by: 'bob@example.com',
  comment: null
};

const ALL_VERSIONS = [VERSION_1, VERSION_2];

describe('ReportVersionView', () => {
  const mockSaveReportVersion = jest.fn();
  let useReportVersion: jest.Mock;
  let useReportVersionsList: jest.Mock;
  let useReportsMutations: jest.Mock;

  // Restore spies after all tests so other test files get the real module.
  afterAll(() => {
    jest.restoreAllMocks();
  });

  beforeEach(() => {
    jest.clearAllMocks();
    // Default: user has reports:write permission.
    mockUsePermissions.mockReturnValue(() => true);
    useReportVersion = jest.spyOn(reportsApiModule, 'useReportVersion') as unknown as jest.Mock;
    useReportVersion.mockReturnValue({ reportVersion: VERSION_1, loading: false, error: null });
    useReportVersionsList = jest.spyOn(reportsApiModule, 'useReportVersionsList') as unknown as jest.Mock;
    useReportVersionsList.mockReturnValue({ versions: ALL_VERSIONS, loading: false, error: null });
    useReportsMutations = jest.spyOn(reportsApiModule, 'useReportsMutations') as unknown as jest.Mock;
    useReportsMutations.mockReturnValue({ saveReportVersion: mockSaveReportVersion });
  });

  afterEach(cleanup);

  // ---------------------------------------------------------------------------
  // Loading / error states
  // ---------------------------------------------------------------------------

  it('shows loading spinner while fetching', () => {
    useReportVersion.mockReturnValue({ reportVersion: undefined, loading: true, error: null });
    render(<ReportVersionView />, { wrapper: Wrapper });

    expect(screen.getByRole('progressbar')).toBeInTheDocument();
  });

  it('shows error message when fetch fails', () => {
    useReportVersion.mockReturnValue({
      reportVersion: undefined,
      loading: false,
      error: new Error('oops')
    });
    render(<ReportVersionView />, { wrapper: Wrapper });

    expect(screen.getByText('Failed to load this version')).toBeInTheDocument();
  });

  // ---------------------------------------------------------------------------
  // Toolbar metadata
  // ---------------------------------------------------------------------------

  it('renders version metadata in the toolbar', () => {
    render(<ReportVersionView />, { wrapper: Wrapper });

    expect(screen.getByText(/v1/)).toBeInTheDocument();
    expect(screen.getByText(/alice@example\.com/)).toBeInTheDocument();
    expect(screen.getByText(/"Initial version"/)).toBeInTheDocument();
  });

  it('shows "Viewing version N of M" subtitle', () => {
    render(<ReportVersionView />, { wrapper: Wrapper });

    expect(screen.getByText('Viewing version 1 of 2')).toBeInTheDocument();
  });

  it('renders the full page without crashing', () => {
    const { container } = render(<ReportVersionView />, { wrapper: Wrapper });

    expect(container.firstChild).not.toBeNull();
  });

  // ---------------------------------------------------------------------------
  // Back navigation
  // ---------------------------------------------------------------------------

  it('navigates back to history list on "Back to history" click', async () => {
    render(<ReportVersionView />, { wrapper: Wrapper });

    fireEvent.click(screen.getByRole('button', { name: /back to history/i }));

    await waitFor(() => {
      expect(screen.getByTestId('nav-location')).toHaveTextContent('/app/reports/r1/history');
    });
  });

  // ---------------------------------------------------------------------------
  // Restore button
  // ---------------------------------------------------------------------------

  it('Restore button is enabled when viewing a non-latest version', () => {
    render(<ReportVersionView />, { wrapper: Wrapper });

    expect(screen.getByRole('button', { name: /restore this version/i })).not.toBeDisabled();
  });

  it('Restore button is disabled when viewing the latest version', () => {
    useReportVersion.mockReturnValue({ reportVersion: VERSION_2, loading: false, error: null });
    render(<ReportVersionView />, { wrapper: makeWrapper('/app/reports/r1/versions/2') });

    expect(screen.getByRole('button', { name: /restore this version/i })).toBeDisabled();
  });

  it('Restore button is disabled when user lacks reports:write', () => {
    mockUsePermissions.mockReturnValue(() => false);
    render(<ReportVersionView />, { wrapper: Wrapper });

    expect(screen.getByRole('button', { name: /restore this version/i })).toBeDisabled();
  });

  it('calls saveReportVersion with correct args and navigates on Restore', async () => {
    mockSaveReportVersion.mockResolvedValue({});
    render(<ReportVersionView />, { wrapper: Wrapper });

    fireEvent.click(screen.getByRole('button', { name: /restore this version/i }));

    await waitFor(() => {
      expect(mockSaveReportVersion).toHaveBeenCalledWith(
        'r1',
        VERSION_1.config,
        'Restored from version 1'
      );
    });

    await waitFor(() => {
      expect(screen.getByTestId('nav-location')).toHaveTextContent('/app/reports/r1');
    });
  });

  it('shows error alert when restore fails', async () => {
    mockSaveReportVersion.mockRejectedValue(new Error('save failed'));
    render(<ReportVersionView />, { wrapper: Wrapper });

    fireEvent.click(screen.getByRole('button', { name: /restore this version/i }));

    await waitFor(() => {
      expect(screen.getByText('save failed')).toBeInTheDocument();
    });
    // Should NOT navigate on failure — still on original path
    expect(screen.getByTestId('nav-location')).toHaveTextContent('/app/reports/r1/versions/1');
  });

  // ---------------------------------------------------------------------------
  // Prev / Next navigation buttons
  // ---------------------------------------------------------------------------

  it('older button is disabled and labeled "Older" on the oldest version', () => {
    // VERSION_1 is oldest — no prev
    render(<ReportVersionView />, { wrapper: Wrapper });

    const olderBtn = screen.getByRole('button', { name: /older/i });
    expect(olderBtn).toBeDisabled();
  });

  it('newer button shows the next version number and navigates on click', async () => {
    // VERSION_1 → next is VERSION_2
    render(<ReportVersionView />, { wrapper: Wrapper });

    const newerBtn = screen.getByRole('button', { name: /v2/i });
    expect(newerBtn).not.toBeDisabled();
    fireEvent.click(newerBtn);

    await waitFor(() => {
      expect(screen.getByTestId('nav-location')).toHaveTextContent('/app/reports/r1/versions/2');
    });
  });

  it('newer button is disabled and labeled "Newer" on the latest version', () => {
    useReportVersion.mockReturnValue({ reportVersion: VERSION_2, loading: false, error: null });
    render(<ReportVersionView />, { wrapper: makeWrapper('/app/reports/r1/versions/2') });

    const newerBtn = screen.getByRole('button', { name: /newer/i });
    expect(newerBtn).toBeDisabled();
  });

  it('older button shows the previous version number and navigates on click', async () => {
    // VERSION_2 → prev is VERSION_1
    useReportVersion.mockReturnValue({ reportVersion: VERSION_2, loading: false, error: null });
    render(<ReportVersionView />, { wrapper: makeWrapper('/app/reports/r1/versions/2') });

    const olderBtn = screen.getByRole('button', { name: /v1/i });
    expect(olderBtn).not.toBeDisabled();
    fireEvent.click(olderBtn);

    await waitFor(() => {
      expect(screen.getByTestId('nav-location')).toHaveTextContent('/app/reports/r1/versions/1');
    });
  });

  it('both nav buttons are disabled when only one version exists', () => {
    useReportVersionsList.mockReturnValue({
      versions: [VERSION_1],
      loading: false,
      error: null
    });
    render(<ReportVersionView />, { wrapper: Wrapper });

    expect(screen.getByRole('button', { name: /older/i })).toBeDisabled();
    expect(screen.getByRole('button', { name: /newer/i })).toBeDisabled();
  });
});
