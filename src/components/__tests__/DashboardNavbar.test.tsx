import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import { ConfigContext } from 'src/config.context';
import DashboardNavbar from '../DashboardNavbar';

jest.mock('src/hooks/useCurrentUser', () => ({
  useCurrentUser: jest.fn(),
}));

import { useCurrentUser } from 'src/hooks/useCurrentUser';

const theme = createTheme();

const mockUseCurrentUser = useCurrentUser as jest.MockedFunction<typeof useCurrentUser>;

function Wrapper({
  contextValue,
  children
}: {
  contextValue: any;
  children: React.ReactNode;
}) {
  return (
    <MemoryRouter>
      <ThemeProvider theme={theme}>
        <ConfigContext.Provider value={contextValue}>
          {children}
        </ConfigContext.Provider>
      </ThemeProvider>
    </MemoryRouter>
  );
}

describe('DashboardNavbar', () => {
  const defaultProps = {
    setConfigUpdate: jest.fn(),
    setConfig: jest.fn(),
    onMobileNavOpen: jest.fn()
  };

  beforeEach(() => {
    jest.clearAllMocks();
    mockUseCurrentUser.mockReturnValue(null);
  });

  afterEach(cleanup);

  it('renders without error', () => {
    const { container } = render(
      <Wrapper contextValue={{}}>
        <DashboardNavbar {...defaultProps} />
      </Wrapper>
    );
    expect(container.firstChild).not.toBeNull();
  });

  it('shows refresh snackbar when configUpdate is defined', () => {
    render(
      <Wrapper contextValue={{}}>
        <DashboardNavbar {...defaultProps} configUpdate={{ some: 'update' } as any} />
      </Wrapper>
    );
    expect(screen.getByText('Settings have changed.')).toBeInTheDocument();
  });

  it('calls setConfig and setConfigUpdate when Refresh is clicked', () => {
    const configUpdate = { some: 'update' } as any;
    render(
      <Wrapper contextValue={{}}>
        <DashboardNavbar {...defaultProps} configUpdate={configUpdate} />
      </Wrapper>
    );
    fireEvent.click(screen.getByText(/refresh/i));
    expect(defaultProps.setConfig).toHaveBeenCalledWith(configUpdate);
    expect(defaultProps.setConfigUpdate).toHaveBeenCalled();
  });

  it('renders no user info when currentUser is null', () => {
    mockUseCurrentUser.mockReturnValue(null);
    const { container } = render(
      <Wrapper contextValue={{}}>
        <DashboardNavbar {...defaultProps} />
      </Wrapper>
    );
    expect(container.querySelector('svg')).toBeNull();
    expect(screen.queryByText(/@/)).toBeNull();
  });

  it('renders display name when user is authenticated', () => {
    mockUseCurrentUser.mockReturnValue({
      user_id: 'uid1',
      sub: 'sub123',
      iss: 'https://idp.example.com',
      email: 'alice@example.com',
      display_name: 'Alice Smith',
      created_at: '2024-01-01T00:00:00+00:00',
      last_login: '2024-01-01T00:00:00+00:00',
      archived_at: null,
    });
    render(
      <Wrapper contextValue={{}}>
        <DashboardNavbar {...defaultProps} />
      </Wrapper>
    );
    expect(screen.getByText('Alice Smith')).toBeInTheDocument();
  });

  it('falls back to email when display_name is null', () => {
    mockUseCurrentUser.mockReturnValue({
      user_id: 'uid1',
      sub: 'sub123',
      iss: 'https://idp.example.com',
      email: 'alice@example.com',
      display_name: null,
      created_at: '2024-01-01T00:00:00+00:00',
      last_login: '2024-01-01T00:00:00+00:00',
      archived_at: null,
    });
    render(
      <Wrapper contextValue={{}}>
        <DashboardNavbar {...defaultProps} />
      </Wrapper>
    );
    expect(screen.getByText('alice@example.com')).toBeInTheDocument();
  });

  it('renders avatar SVG when user is authenticated', () => {
    mockUseCurrentUser.mockReturnValue({
      user_id: 'uid1',
      sub: 'sub123',
      iss: 'https://idp.example.com',
      email: 'alice@example.com',
      display_name: 'Alice Smith',
      created_at: '2024-01-01T00:00:00+00:00',
      last_login: '2024-01-01T00:00:00+00:00',
      archived_at: null,
    });
    const { container } = render(
      <Wrapper contextValue={{}}>
        <DashboardNavbar {...defaultProps} />
      </Wrapper>
    );
    expect(container.querySelector('svg')).not.toBeNull();
  });

  it('renders email when auth is disabled (no display_name)', () => {
    mockUseCurrentUser.mockReturnValue({
      user_id: 'uid-dev',
      sub: 'dev@example.com',
      iss: 'dev',
      email: 'dev@example.com',
      display_name: null,
      created_at: '2024-01-01T00:00:00+00:00',
      last_login: '2024-01-01T00:00:00+00:00',
      archived_at: null,
    });
    render(
      <Wrapper contextValue={{}}>
        <DashboardNavbar {...defaultProps} />
      </Wrapper>
    );
    expect(screen.getByText('dev@example.com')).toBeInTheDocument();
  });
});
