import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import ReportVersionView from 'src/pages/ReportVersionView';

jest.mock('react-helmet', () => ({
  Helmet: ({ children }: { children: React.ReactNode }) => <>{children}</>
}));

jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  useParams: jest.fn(),
  useNavigate: jest.fn()
}));

jest.mock('src/hooks/useReportsApi', () => ({
  useReportVersion: jest.fn(),
  useReportVersionsList: jest.fn(),
  useReportsMutations: jest.fn()
}));

// ReportView renders live panels with Cypher queries — stub it out.
jest.mock('src/components/ReportView', () => ({
  __esModule: true,
  default: ({ title }: { title: string }) => <div data-testid="report-view">{title}</div>
}));

const { useParams, useNavigate } = require('react-router-dom');
const { useReportVersion, useReportVersionsList, useReportsMutations } =
  require('src/hooks/useReportsApi');

const theme = createTheme();
function Wrapper({ children }: { children: React.ReactNode }) {
  return (
    <MemoryRouter>
      <ThemeProvider theme={theme}>{children}</ThemeProvider>
    </MemoryRouter>
  );
}

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
  const mockNavigate = jest.fn();
  const mockSaveReportVersion = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    useParams.mockReturnValue({ id: 'r1', version: '1' });
    useNavigate.mockReturnValue(mockNavigate);
    useReportVersion.mockReturnValue({ reportVersion: VERSION_1, loading: false, error: null });
    useReportVersionsList.mockReturnValue({ versions: ALL_VERSIONS, loading: false, error: null });
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

  it('renders the report content via ReportView', () => {
    render(<ReportVersionView />, { wrapper: Wrapper });

    expect(screen.getByTestId('report-view')).toHaveTextContent('My Report');
  });

  // ---------------------------------------------------------------------------
  // Back navigation
  // ---------------------------------------------------------------------------

  it('navigates back to history list on "Back to history" click', () => {
    render(<ReportVersionView />, { wrapper: Wrapper });

    fireEvent.click(screen.getByRole('button', { name: /back to history/i }));
    expect(mockNavigate).toHaveBeenCalledWith('/app/reports/r1/history');
  });

  // ---------------------------------------------------------------------------
  // Restore button
  // ---------------------------------------------------------------------------

  it('Restore button is enabled when viewing a non-latest version', () => {
    render(<ReportVersionView />, { wrapper: Wrapper });

    expect(screen.getByRole('button', { name: /restore this version/i })).not.toBeDisabled();
  });

  it('Restore button is disabled when viewing the latest version', () => {
    useParams.mockReturnValue({ id: 'r1', version: '2' });
    useReportVersion.mockReturnValue({ reportVersion: VERSION_2, loading: false, error: null });
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
      expect(mockNavigate).toHaveBeenCalledWith('/app/reports/r1');
    });
  });

  it('shows error alert when restore fails', async () => {
    mockSaveReportVersion.mockRejectedValue(new Error('save failed'));
    render(<ReportVersionView />, { wrapper: Wrapper });

    fireEvent.click(screen.getByRole('button', { name: /restore this version/i }));

    await waitFor(() => {
      expect(screen.getByText('save failed')).toBeInTheDocument();
    });
    // Should NOT navigate on failure
    expect(mockNavigate).not.toHaveBeenCalled();
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

  it('newer button shows the next version number and navigates on click', () => {
    // VERSION_1 → next is VERSION_2
    render(<ReportVersionView />, { wrapper: Wrapper });

    const newerBtn = screen.getByRole('button', { name: /v2/i });
    expect(newerBtn).not.toBeDisabled();
    fireEvent.click(newerBtn);
    expect(mockNavigate).toHaveBeenCalledWith('/app/reports/r1/versions/2');
  });

  it('newer button is disabled and labeled "Newer" on the latest version', () => {
    useParams.mockReturnValue({ id: 'r1', version: '2' });
    useReportVersion.mockReturnValue({ reportVersion: VERSION_2, loading: false, error: null });
    render(<ReportVersionView />, { wrapper: Wrapper });

    const newerBtn = screen.getByRole('button', { name: /newer/i });
    expect(newerBtn).toBeDisabled();
  });

  it('older button shows the previous version number and navigates on click', () => {
    // VERSION_2 → prev is VERSION_1
    useParams.mockReturnValue({ id: 'r1', version: '2' });
    useReportVersion.mockReturnValue({ reportVersion: VERSION_2, loading: false, error: null });
    render(<ReportVersionView />, { wrapper: Wrapper });

    const olderBtn = screen.getByRole('button', { name: /v1/i });
    expect(olderBtn).not.toBeDisabled();
    fireEvent.click(olderBtn);
    expect(mockNavigate).toHaveBeenCalledWith('/app/reports/r1/versions/1');
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
