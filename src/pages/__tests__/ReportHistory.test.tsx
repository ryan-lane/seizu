import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import ReportHistory from 'src/pages/ReportHistory';

jest.mock('react-helmet', () => ({
  Helmet: ({ children }: { children: React.ReactNode }) => <>{children}</>
}));

jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  useParams: jest.fn(),
  useNavigate: jest.fn()
}));

jest.mock('src/hooks/useReportsApi', () => ({
  useReportVersionsList: jest.fn(),
  useReportsMutations: jest.fn()
}));

const { useParams, useNavigate } = require('react-router-dom');
const { useReportVersionsList, useReportsMutations } = require('src/hooks/useReportsApi');

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

describe('ReportHistory', () => {
  const mockNavigate = jest.fn();
  const mockSaveReportVersion = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    useParams.mockReturnValue({ id: 'r1' });
    useNavigate.mockReturnValue(mockNavigate);
    useReportVersionsList.mockReturnValue({
      versions: [VERSION_1, VERSION_2],
      loading: false,
      error: null
    });
    useReportsMutations.mockReturnValue({ saveReportVersion: mockSaveReportVersion });
  });

  afterEach(cleanup);

  it('renders versions sorted newest-first', () => {
    render(<ReportHistory />, { wrapper: Wrapper });

    const rows = screen.getAllByRole('row');
    // header + 2 data rows
    expect(rows).toHaveLength(3);
    expect(rows[1]).toHaveTextContent('v2');
    expect(rows[2]).toHaveTextContent('v1');
  });

  it('labels the latest version as current', () => {
    render(<ReportHistory />, { wrapper: Wrapper });

    const rows = screen.getAllByRole('row');
    expect(rows[1]).toHaveTextContent('current');
    expect(rows[2]).not.toHaveTextContent('current');
  });

  it('renders version numbers as links to the version view', () => {
    render(<ReportHistory />, { wrapper: Wrapper });

    expect(screen.getByRole('link', { name: 'v2' })).toHaveAttribute(
      'href',
      '/app/reports/r1/versions/2'
    );
    expect(screen.getByRole('link', { name: 'v1' })).toHaveAttribute(
      'href',
      '/app/reports/r1/versions/1'
    );
  });

  it('shows comment text in the row', () => {
    render(<ReportHistory />, { wrapper: Wrapper });

    expect(screen.getByText('Initial version')).toBeInTheDocument();
  });

  it('shows em-dash for a null comment', () => {
    render(<ReportHistory />, { wrapper: Wrapper });

    expect(screen.getAllByText('—')).toHaveLength(1);
  });

  it('shows the report name in the heading', () => {
    render(<ReportHistory />, { wrapper: Wrapper });

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(
      'Version history – My Report'
    );
  });

  it('navigates back to the report on "Back to report" click', () => {
    render(<ReportHistory />, { wrapper: Wrapper });

    fireEvent.click(screen.getByRole('button', { name: /back to report/i }));
    expect(mockNavigate).toHaveBeenCalledWith('/app/reports/r1');
  });

  it('shows loading spinner while loading', () => {
    useReportVersionsList.mockReturnValue({ versions: [], loading: true, error: null });
    render(<ReportHistory />, { wrapper: Wrapper });

    expect(screen.getByRole('progressbar')).toBeInTheDocument();
  });

  it('shows error message when fetch fails', () => {
    useReportVersionsList.mockReturnValue({
      versions: [],
      loading: false,
      error: new Error('oops')
    });
    render(<ReportHistory />, { wrapper: Wrapper });

    expect(screen.getByText('Failed to load version history')).toBeInTheDocument();
  });

  it('shows "No versions found" when versions list is empty', () => {
    useReportVersionsList.mockReturnValue({ versions: [], loading: false, error: null });
    render(<ReportHistory />, { wrapper: Wrapper });

    expect(screen.getByText('No versions found.')).toBeInTheDocument();
  });

  it('opens the per-row menu and navigates to version view on View click', () => {
    render(<ReportHistory />, { wrapper: Wrapper });

    // Open menu for the first data row (v2, the current version)
    const menuButtons = screen.getAllByRole('button', { name: 'More actions' });
    fireEvent.click(menuButtons[0]);

    fireEvent.click(screen.getByRole('menuitem', { name: /view/i }));
    expect(mockNavigate).toHaveBeenCalledWith('/app/reports/r1/versions/2');
  });

  it('Restore menu item is disabled for the current version', () => {
    render(<ReportHistory />, { wrapper: Wrapper });

    // Open menu for the first data row (v2, the current/latest version)
    const menuButtons = screen.getAllByRole('button', { name: 'More actions' });
    fireEvent.click(menuButtons[0]);

    expect(screen.getByRole('menuitem', { name: /restore/i })).toHaveAttribute(
      'aria-disabled',
      'true'
    );
  });

  it('Restore menu item is enabled for a non-current version', () => {
    render(<ReportHistory />, { wrapper: Wrapper });

    // Open menu for the second data row (v1, not current)
    const menuButtons = screen.getAllByRole('button', { name: 'More actions' });
    fireEvent.click(menuButtons[1]);

    expect(screen.getByRole('menuitem', { name: /restore/i })).not.toHaveAttribute(
      'aria-disabled',
      'true'
    );
  });

  it('calls saveReportVersion and navigates when Restore is clicked', async () => {
    mockSaveReportVersion.mockResolvedValue({});
    render(<ReportHistory />, { wrapper: Wrapper });

    // Open menu for v1 row (not current)
    const menuButtons = screen.getAllByRole('button', { name: 'More actions' });
    fireEvent.click(menuButtons[1]);
    fireEvent.click(screen.getByRole('menuitem', { name: /restore/i }));

    await waitFor(() => {
      expect(mockSaveReportVersion).toHaveBeenCalledWith(
        'r1',
        VERSION_1.config,
        'Restored from version 1'
      );
      expect(mockNavigate).toHaveBeenCalledWith('/app/reports/r1');
    });
  });
});
