import { render, screen, fireEvent, cleanup, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import { AuthConfigContext, type AuthConfig } from 'src/authConfig.context';
import DashboardNavbar from '../DashboardNavbar';

jest.mock('src/hooks/useCurrentUser', () => ({
  useCurrentUser: jest.fn(),
}));

import { useCurrentUser } from 'src/hooks/useCurrentUser';

const theme = createTheme();

const mockUseCurrentUser = useCurrentUser as jest.MockedFunction<typeof useCurrentUser>;

function Wrapper({
  authConfig,
  children
}: {
  authConfig?: AuthConfig;
  children: React.ReactNode;
}) {
  return (
    <MemoryRouter>
      <ThemeProvider theme={theme}>
        <AuthConfigContext.Provider value={authConfig ?? { auth_required: false, oidc: null, userManager: null }}>
          {children}
        </AuthConfigContext.Provider>
      </ThemeProvider>
    </MemoryRouter>
  );
}

const CURRENT_USER = {
  user_id: 'uid1',
  sub: 'sub123',
  iss: 'https://idp.example.com',
  email: 'alice@example.com',
  display_name: 'Alice Smith',
  created_at: '2024-01-01T00:00:00+00:00',
  last_login: '2024-01-01T00:00:00+00:00',
  archived_at: null,
  permissions: [],
};

describe('DashboardNavbar', () => {
  const defaultProps = {
    onMobileNavOpen: jest.fn()
  };

  beforeEach(() => {
    jest.clearAllMocks();
    mockUseCurrentUser.mockReturnValue(null);
  });

  afterEach(cleanup);

  it('renders without error', () => {
    const { container } = render(
      <Wrapper>
        <DashboardNavbar {...defaultProps} />
      </Wrapper>
    );
    expect(container.firstChild).not.toBeNull();
  });

  it('calls the sidebar toggle handler from the desktop collapse button', () => {
    const onSidebarToggle = jest.fn();
    render(
      <Wrapper>
        <DashboardNavbar
          {...defaultProps}
          onSidebarToggle={onSidebarToggle}
        />
      </Wrapper>
    );

    fireEvent.click(screen.getByRole('button', { name: /collapse sidebar/i }));

    expect(onSidebarToggle).toHaveBeenCalledTimes(1);
  });

  it('renders no user info when currentUser is null', () => {
    mockUseCurrentUser.mockReturnValue(null);
    const { container } = render(
      <Wrapper>
        <DashboardNavbar {...defaultProps} />
      </Wrapper>
    );
    expect(container.querySelector('svg')).toBeNull();
    expect(screen.queryByText(/@/)).toBeNull();
  });

  it('renders email when user is authenticated', () => {
    mockUseCurrentUser.mockReturnValue(CURRENT_USER);
    render(
      <Wrapper>
        <DashboardNavbar {...defaultProps} />
      </Wrapper>
    );
    expect(screen.getByText('alice@example.com')).toBeInTheDocument();
  });

  it('falls back to display_name when email is empty', () => {
    mockUseCurrentUser.mockReturnValue({
      user_id: 'uid1',
      sub: 'sub123',
      iss: 'https://idp.example.com',
      email: '',
      display_name: 'Alice Smith',
      created_at: '2024-01-01T00:00:00+00:00',
      last_login: '2024-01-01T00:00:00+00:00',
      archived_at: null,
      permissions: [],
    });
    render(
      <Wrapper>
        <DashboardNavbar {...defaultProps} />
      </Wrapper>
    );
    expect(screen.getByText('Alice Smith')).toBeInTheDocument();
  });

  it('falls back to user_id when email and display_name are empty', () => {
    mockUseCurrentUser.mockReturnValue({
      user_id: 'uid1',
      sub: 'sub123',
      iss: 'https://idp.example.com',
      email: '',
      display_name: null,
      created_at: '2024-01-01T00:00:00+00:00',
      last_login: '2024-01-01T00:00:00+00:00',
      archived_at: null,
      permissions: [],
    });
    render(
      <Wrapper>
        <DashboardNavbar {...defaultProps} />
      </Wrapper>
    );
    expect(screen.getByText('uid1')).toBeInTheDocument();
  });

  it('renders avatar SVG when user is authenticated', () => {
    mockUseCurrentUser.mockReturnValue(CURRENT_USER);
    const { container } = render(
      <Wrapper>
        <DashboardNavbar {...defaultProps} />
      </Wrapper>
    );
    expect(container.querySelector('svg')).not.toBeNull();
  });

  it('opens the user menu from the avatar button', () => {
    mockUseCurrentUser.mockReturnValue(CURRENT_USER);
    render(
      <Wrapper>
        <DashboardNavbar {...defaultProps} />
      </Wrapper>
    );

    fireEvent.click(screen.getByRole('button', { name: /user menu/i }));

    expect(screen.getByRole('menu')).toBeInTheDocument();
    expect(screen.getAllByText('alice@example.com').length).toBeGreaterThan(1);
  });

  it('calls OIDC signoutRedirect when Log out is clicked', async () => {
    mockUseCurrentUser.mockReturnValue(CURRENT_USER);
    const signoutRedirect = jest.fn().mockResolvedValue(undefined);
    const removeUser = jest.fn().mockResolvedValue(undefined);
    render(
      <Wrapper
        authConfig={{
          auth_required: true,
          oidc: null,
          userManager: { signoutRedirect, removeUser } as any,
        }}
      >
        <DashboardNavbar {...defaultProps} />
      </Wrapper>
    );

    fireEvent.click(screen.getByRole('button', { name: /user menu/i }));
    fireEvent.click(screen.getByRole('menuitem', { name: /log out/i }));

    await waitFor(() => {
      expect(signoutRedirect).toHaveBeenCalledWith({
        post_logout_redirect_uri: window.location.origin,
      });
    });
    expect(removeUser).not.toHaveBeenCalled();
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
      permissions: [],
    });
    render(
      <Wrapper>
        <DashboardNavbar {...defaultProps} />
      </Wrapper>
    );
    expect(screen.getByText('dev@example.com')).toBeInTheDocument();
  });
});
