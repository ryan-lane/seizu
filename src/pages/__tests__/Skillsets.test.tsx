import { cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import Skillsets from 'src/pages/Skillsets';
import * as skillsetsApiModule from 'src/hooks/useSkillsetsApi';
import * as permissionsModule from 'src/hooks/usePermissions';

jest.mock('src/hooks/usePermissions', () => ({
  usePermissions: jest.fn(),
}));

jest.mock('src/hooks/useSkillsetsApi', () => ({
  useSkillsetsList: jest.fn(),
  useSkillsetMutations: jest.fn(),
}));

jest.mock('src/components/UserDisplay', () => ({
  __esModule: true,
  default: ({ userId }: { userId: string }) => <>{userId}</>,
}));

const mockUsePermissions = permissionsModule.usePermissions as jest.MockedFunction<typeof permissionsModule.usePermissions>;
const mockUseSkillsetsList = skillsetsApiModule.useSkillsetsList as unknown as jest.Mock;
const mockUseSkillsetMutations = skillsetsApiModule.useSkillsetMutations as unknown as jest.Mock;
const theme = createTheme();

const SKILLSET: skillsetsApiModule.SkillsetListItem = {
  skillset_id: 'responders',
  name: 'Responders',
  description: 'Incident response skills',
  enabled: true,
  current_version: 2,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-02T00:00:00Z',
  created_by: 'alice',
  updated_by: 'bob',
};

function Wrapper({ children }: { children: React.ReactNode }) {
  return (
    <MemoryRouter initialEntries={['/app/skillsets']}>
      <ThemeProvider theme={theme}>
        <Routes>
          <Route path="/app/skillsets" element={<>{children}</>} />
        </Routes>
      </ThemeProvider>
    </MemoryRouter>
  );
}

describe('Skillsets', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockUsePermissions.mockReturnValue((permission: string) => permission.startsWith('skillsets:'));
    mockUseSkillsetsList.mockReturnValue({
      skillsets: [SKILLSET],
      loading: false,
      error: null,
      refresh: jest.fn(),
    });
    mockUseSkillsetMutations.mockReturnValue({
      createSkillset: jest.fn(),
      updateSkillset: jest.fn(),
      deleteSkillset: jest.fn(),
    });
  });

  afterEach(cleanup);

  it('renders skillset update metadata columns consistently', () => {
    render(<Skillsets />, { wrapper: Wrapper });

    expect(screen.getByText('Last updated')).toBeInTheDocument();
    expect(screen.getByText('Updated by')).toBeInTheDocument();
    expect(screen.getByText('Responders')).toBeInTheDocument();
    expect(screen.getByText('v2')).toBeInTheDocument();
    expect(screen.getByText('bob')).toBeInTheDocument();
  });
});
