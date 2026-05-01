import { render, screen, cleanup } from '@testing-library/react';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import QueryConsole from 'src/pages/QueryConsole';
import * as usePermissionsModule from 'src/hooks/usePermissions';

jest.mock('src/hooks/usePermissions', () => ({
  usePermissionState: jest.fn(),
}));

jest.mock('src/components/QueryConsoleSchemaPanel', () => ({
  __esModule: true,
  default: () => <div data-testid="schema-panel" />,
}));

jest.mock('src/components/reports/CypherGraph', () => ({
  __esModule: true,
  default: () => <div data-testid="cypher-graph" />,
}));

const mockUsePermissionState = usePermissionsModule.usePermissionState as jest.MockedFunction<typeof usePermissionsModule.usePermissionState>;
const theme = createTheme();

function Wrapper({ children }: { children: React.ReactNode }) {
  return <ThemeProvider theme={theme}>{children}</ThemeProvider>;
}

describe('QueryConsole', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  afterEach(cleanup);

  it('shows a spinner while permissions are loading', () => {
    mockUsePermissionState.mockReturnValue({ hasPermission: () => false, loading: true, currentUser: null });

    render(<QueryConsole />, { wrapper: Wrapper });

    expect(screen.getByRole('progressbar')).toBeInTheDocument();
    expect(screen.queryByText('You do not have access to the query console.')).not.toBeInTheDocument();
  });

  it('shows no-access message when loaded without query permission', () => {
    mockUsePermissionState.mockReturnValue({ hasPermission: () => false, loading: false, currentUser: null });

    render(<QueryConsole />, { wrapper: Wrapper });

    expect(screen.getByText('You do not have access to the query console.')).toBeInTheDocument();
  });

  it('renders the console when query permission is present', () => {
    mockUsePermissionState.mockReturnValue({
      hasPermission: (permission: string) => permission === 'query:execute',
      loading: false,
      currentUser: null,
    });

    render(<QueryConsole />, { wrapper: Wrapper });

    expect(screen.getByTestId('schema-panel')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Enter a Cypher query... (Ctrl+Enter to run)')).toBeInTheDocument();
  });
});
