import { render, screen, fireEvent, cleanup, within } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import Roles from 'src/pages/Roles';
import * as rolesApiModule from 'src/hooks/useRolesApi';
import * as usePermissionsModule from 'src/hooks/usePermissions';

jest.mock('src/hooks/usePermissions', () => ({
  usePermissions: jest.fn(),
}));

jest.mock('src/hooks/useRolesApi', () => {
  return {
    isBuiltinRole: (roleId: string) => roleId.startsWith('builtin:'),
    useBuiltinRolesList: jest.fn(),
    useRolesList: jest.fn(),
    useRoleMutations: jest.fn(),
  };
});

jest.mock('src/components/UserDisplay', () => ({
  __esModule: true,
  default: ({ userId }: { userId: string }) => <>{userId}</>,
}));

const mockUsePermissions = usePermissionsModule.usePermissions as jest.MockedFunction<typeof usePermissionsModule.usePermissions>;
const mockUseBuiltinRolesList = rolesApiModule.useBuiltinRolesList as unknown as jest.Mock;
const mockUseRolesList = rolesApiModule.useRolesList as unknown as jest.Mock;
const mockUseRoleMutations = rolesApiModule.useRoleMutations as unknown as jest.Mock;
const theme = createTheme();

const BUILTIN_ROLE: rolesApiModule.RoleItem = {
  role_id: 'builtin:seizu-viewer',
  name: 'seizu-viewer',
  description: 'Built-in role: seizu-viewer.',
  permissions: ['reports:read', 'roles:read'],
  current_version: 0,
  created_at: '',
  updated_at: '',
  created_by: 'system',
  updated_by: null,
};

const CUSTOM_ROLE: rolesApiModule.RoleItem = {
  role_id: 'role1',
  name: 'Security Operator',
  description: 'Can inspect and run approved tools.',
  permissions: ['reports:read', 'tools:call', 'tools:read'],
  current_version: 2,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-02T00:00:00Z',
  created_by: 'alice',
  updated_by: 'bob',
};

function Wrapper({ children }: { children: React.ReactNode }) {
  return (
    <MemoryRouter initialEntries={['/app/roles']}>
      <ThemeProvider theme={theme}>
        <Routes>
          <Route path="/app/roles" element={<>{children}</>} />
        </Routes>
      </ThemeProvider>
    </MemoryRouter>
  );
}

function setPermissions(permissions: string[]) {
  mockUsePermissions.mockReturnValue((permission: string) => permissions.includes(permission));
}

describe('Roles', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    setPermissions(['roles:read', 'roles:write', 'roles:delete']);
    mockUseBuiltinRolesList.mockReturnValue({
      roles: [BUILTIN_ROLE],
      loading: false,
      error: null,
      refresh: jest.fn(),
    });
    mockUseRolesList.mockReturnValue({
      roles: [CUSTOM_ROLE],
      loading: false,
      error: null,
      refresh: jest.fn(),
    });
    mockUseRoleMutations.mockReturnValue({
      createRole: jest.fn(),
      updateRole: jest.fn(),
      deleteRole: jest.fn(),
    });
  });

  afterEach(cleanup);

  it('shows a no-access message without roles:read', () => {
    setPermissions([]);

    render(<Roles />, { wrapper: Wrapper });

    expect(screen.getByText('You do not have access to role management.')).toBeInTheDocument();
  });

  it('renders built-in and user-defined roles together', () => {
    render(<Roles />, { wrapper: Wrapper });

    expect(screen.getByRole('button', { name: 'seizu-viewer' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Security Operator' })).toBeInTheDocument();
    expect(screen.getByText('Built-in')).toBeInTheDocument();
    expect(screen.getByText('User-defined')).toBeInTheDocument();
    expect(screen.getByText('v2')).toBeInTheDocument();
  });

  it('opens a read-only detail dialog from a role name', () => {
    render(<Roles />, { wrapper: Wrapper });

    fireEvent.click(screen.getByRole('button', { name: 'seizu-viewer' }));

    const dialog = screen.getByRole('dialog', { name: 'seizu-viewer' });
    expect(within(dialog).getByText('Built-in role: seizu-viewer.')).toBeInTheDocument();
    expect(within(dialog).getByText('reports:read')).toBeInTheDocument();
    expect(within(dialog).getByText('roles:read')).toBeInTheDocument();
  });

  it('disables edit, delete, and history actions for built-in roles', () => {
    render(<Roles />, { wrapper: Wrapper });

    fireEvent.click(screen.getAllByRole('button', { name: 'More actions' })[0]);

    expect(screen.getByRole('menuitem', { name: /view detail/i })).not.toHaveAttribute('aria-disabled', 'true');
    expect(screen.getByRole('menuitem', { name: /^edit$/i })).toHaveAttribute('aria-disabled', 'true');
    expect(screen.getByRole('menuitem', { name: /view history/i })).toHaveAttribute('aria-disabled', 'true');
    expect(screen.getByRole('menuitem', { name: /^delete$/i })).toHaveAttribute('aria-disabled', 'true');
  });

  it('hides and disables user-defined role controls based on write/delete permissions', () => {
    setPermissions(['roles:read']);
    render(<Roles />, { wrapper: Wrapper });

    expect(screen.queryByRole('button', { name: /new role/i })).not.toBeInTheDocument();

    fireEvent.click(screen.getAllByRole('button', { name: 'More actions' })[1]);

    expect(screen.getByRole('menuitem', { name: /^edit$/i })).toHaveAttribute('aria-disabled', 'true');
    expect(screen.getByRole('menuitem', { name: /^delete$/i })).toHaveAttribute('aria-disabled', 'true');
    expect(screen.getByRole('menuitem', { name: /view history/i })).not.toHaveAttribute('aria-disabled', 'true');
  });

  it('enables create, edit, and delete controls with write/delete permissions', () => {
    render(<Roles />, { wrapper: Wrapper });

    expect(screen.getByRole('button', { name: /new role/i })).toBeInTheDocument();

    fireEvent.click(screen.getAllByRole('button', { name: 'More actions' })[1]);

    expect(screen.getByRole('menuitem', { name: /^edit$/i })).not.toHaveAttribute('aria-disabled', 'true');
    expect(screen.getByRole('menuitem', { name: /^delete$/i })).not.toHaveAttribute('aria-disabled', 'true');
  });
});
