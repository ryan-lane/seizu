import { cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import Reports from 'src/pages/Reports';
import * as reportsApiModule from 'src/hooks/useReportsApi';
import * as permissionsModule from 'src/hooks/usePermissions';

jest.mock('src/hooks/usePermissions', () => ({
  usePermissionState: jest.fn(),
}));

const theme = createTheme();
const mockUsePermissionState = permissionsModule.usePermissionState as jest.MockedFunction<typeof permissionsModule.usePermissionState>;

function Wrapper({ children }: { children: React.ReactNode }) {
  return (
    <MemoryRouter initialEntries={['/app/reports/r1?edit=true']}>
      <ThemeProvider theme={theme}>
        <Routes>
          <Route path="/app/reports/:id" element={children} />
        </Routes>
      </ThemeProvider>
    </MemoryRouter>
  );
}

describe('Reports', () => {
  let mockUseReport: jest.Mock;
  let mockUseReportsMutations: jest.Mock;

  beforeEach(() => {
    jest.clearAllMocks();
    mockUseReport = jest.spyOn(reportsApiModule, 'useReport') as unknown as jest.Mock;
    mockUseReportsMutations = jest.spyOn(reportsApiModule, 'useReportsMutations') as unknown as jest.Mock;
    mockUsePermissionState.mockReturnValue({
      hasPermission: () => true,
      loading: false,
      currentUser: {
        user_id: 'owner',
        sub: 'owner',
        iss: 'test',
        email: 'owner@example.com',
        display_name: 'Owner',
        created_at: '2026-01-01T00:00:00Z',
        last_login: '2026-01-02T00:00:00Z',
        archived_at: null,
        permissions: [],
      },
    });
    mockUseReport.mockReturnValue({
      report: {
        schema_version: 1,
        rows: [],
      },
      name: 'Metadata Report Name',
      reportVersion: {
        report_id: 'r1',
        name: 'Metadata Report Name',
        version: 1,
        config: { schema_version: 1, rows: [] },
        created_at: '2026-01-01T00:00:00Z',
        created_by: 'owner',
        report_created_by: 'owner',
        report_updated_by: 'owner',
        access: { scope: 'private' },
        comment: null,
      },
      queryCapabilities: {},
      loading: false,
      error: null,
    });
    mockUseReportsMutations.mockReturnValue({
      saveReportVersion: jest.fn(),
      cloneReport: jest.fn(),
      updateReportAccess: jest.fn(),
    });
  });

  afterEach(() => {
    cleanup();
    mockUseReport.mockRestore?.();
    mockUseReportsMutations.mockRestore?.();
  });

  it('populates edit-mode report name from report metadata when config name is absent', () => {
    render(<Reports />, { wrapper: Wrapper });

    expect(screen.getByLabelText('Report name')).toHaveValue('Metadata Report Name');
  });
});
