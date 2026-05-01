import { render, screen, cleanup } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import DashboardSidebar from 'src/components/DashboardSidebar';
import * as reportsApiModule from 'src/hooks/useReportsApi';
import * as usePermissionsModule from 'src/hooks/usePermissions';

jest.mock('src/hooks/usePermissions', () => ({
  usePermissions: jest.fn(),
}));

const mockUsePermissions = usePermissionsModule.usePermissions as jest.MockedFunction<typeof usePermissionsModule.usePermissions>;
const lightTheme = createTheme({ palette: { mode: 'light' } });
const darkTheme = createTheme({ palette: { mode: 'dark' } });

function Wrapper({
  children,
  theme = lightTheme
}: {
  children: React.ReactNode;
  theme?: ReturnType<typeof createTheme>;
}) {
  return (
    <MemoryRouter>
      <ThemeProvider theme={theme}>{children}</ThemeProvider>
    </MemoryRouter>
  );
}

function renderSidebar(permissions: string[]) {
  mockUsePermissions.mockReturnValue((permission: string) => permissions.includes(permission));
  return render(<DashboardSidebar />, { wrapper: Wrapper });
}

describe('DashboardSidebar', () => {
  let useReportsList: jest.Mock;

  beforeEach(() => {
    jest.clearAllMocks();
    useReportsList = jest.spyOn(reportsApiModule, 'useReportsList') as unknown as jest.Mock;
    useReportsList.mockReturnValue({ reports: [], loading: false, error: null, refresh: jest.fn() });
  });

  afterEach(cleanup);

  it('hides Roles when roles:read is absent', () => {
    renderSidebar([]);

    expect(screen.queryByRole('link', { name: 'Roles' })).not.toBeInTheDocument();
  });

  it('shows Roles when roles:read is present', () => {
    renderSidebar(['roles:read']);

    expect(screen.getByRole('link', { name: 'Roles' })).toHaveAttribute('href', '/app/roles');
  });

  it('renders the full logo in the expanded sidebar', () => {
    mockUsePermissions.mockReturnValue(() => false);

    render(<DashboardSidebar />, { wrapper: Wrapper });

    expect(screen.getByAltText('Seizu')).toHaveAttribute('src', '/static/images/logo-horizontal-black.svg');
  });

  it('renders the mark in the collapsed sidebar', () => {
    mockUsePermissions.mockReturnValue(() => false);

    render(<DashboardSidebar collapsed />, { wrapper: Wrapper });

    expect(screen.getByAltText('Seizu')).toHaveAttribute('src', '/static/images/logo-mark-light.svg');
  });

  it('uses dark-surface logo assets in dark mode', () => {
    mockUsePermissions.mockReturnValue(() => false);

    render(
      <Wrapper theme={darkTheme}>
        <DashboardSidebar />
      </Wrapper>
    );

    expect(screen.getByAltText('Seizu')).toHaveAttribute('src', '/static/images/logo-horizontal-white.svg');
  });

  it('uses the dark-surface mark in dark mode when collapsed', () => {
    mockUsePermissions.mockReturnValue(() => false);

    render(
      <Wrapper theme={darkTheme}>
        <DashboardSidebar collapsed />
      </Wrapper>
    );

    expect(screen.getByAltText('Seizu')).toHaveAttribute('src', '/static/images/logo-mark.svg');
  });
});
