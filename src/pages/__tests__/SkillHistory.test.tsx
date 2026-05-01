import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import SkillHistory from 'src/pages/SkillHistory';
import * as skillsetsApiModule from 'src/hooks/useSkillsetsApi';
import * as usePermissionsModule from 'src/hooks/usePermissions';

jest.mock('src/hooks/usePermissions', () => ({
  usePermissions: jest.fn(),
}));

jest.mock('src/hooks/useSkillsetsApi', () => ({
  useSkillVersionsList: jest.fn(),
  useSkillMutations: jest.fn(),
}));

jest.mock('src/components/UserDisplay', () => ({
  __esModule: true,
  default: ({ userId }: { userId: string }) => <>{userId}</>,
}));

jest.mock('react-helmet', () => ({
  Helmet: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

const mockUsePermissions = usePermissionsModule.usePermissions as jest.MockedFunction<typeof usePermissionsModule.usePermissions>;
const mockUseSkillVersionsList = skillsetsApiModule.useSkillVersionsList as unknown as jest.Mock;
const mockUseSkillMutations = skillsetsApiModule.useSkillMutations as unknown as jest.Mock;
const theme = createTheme();

const VERSION_1: skillsetsApiModule.SkillVersion = {
  skill_id: 'skill1',
  skillset_id: 'skillset1',
  name: 'Summarize Findings',
  description: 'Older prompt',
  template: 'Older template',
  parameters: [{ name: 'limit', type: 'integer', description: 'Result limit', required: false, default: 10 }],
  triggers: ['summarize'],
  tools_required: ['graph__query'],
  enabled: false,
  version: 1,
  created_at: '2026-01-01T00:00:00Z',
  created_by: 'alice',
  comment: 'Initial version',
};

const VERSION_2: skillsetsApiModule.SkillVersion = {
  skill_id: 'skill1',
  skillset_id: 'skillset1',
  name: 'Summarize Findings',
  description: 'Current prompt',
  template: 'Current template',
  parameters: [],
  triggers: [],
  tools_required: [],
  enabled: true,
  version: 2,
  created_at: '2026-01-02T00:00:00Z',
  created_by: 'bob',
  comment: null,
};

function TestLocation() {
  const { pathname } = useLocation();
  return <div data-testid="nav-location" style={{ display: 'none' }}>{pathname}</div>;
}

function Wrapper({ children }: { children: React.ReactNode }) {
  return (
    <MemoryRouter initialEntries={['/app/skillsets/skillset1/skills/skill1/history']}>
      <ThemeProvider theme={theme}>
        <TestLocation />
        <Routes>
          <Route path="/app/skillsets/:skillsetId/skills/:skillId/history" element={<>{children}</>} />
          <Route path="/app/skillsets/:skillsetId/skills" element={<div />} />
        </Routes>
      </ThemeProvider>
    </MemoryRouter>
  );
}

describe('SkillHistory', () => {
  const updateSkill = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    mockUsePermissions.mockReturnValue((permission: string) => permission === 'skills:write');
    mockUseSkillVersionsList.mockReturnValue({
      versions: [VERSION_1, VERSION_2],
      loading: false,
      error: null,
    });
    updateSkill.mockResolvedValue({});
    mockUseSkillMutations.mockReturnValue({ updateSkill });
  });

  afterEach(cleanup);

  it('disables restore for the current version', () => {
    render(<SkillHistory />, { wrapper: Wrapper });

    fireEvent.click(screen.getAllByRole('button', { name: 'More actions' })[0]);

    expect(screen.getByRole('menuitem', { name: /restore/i })).toHaveAttribute('aria-disabled', 'true');
  });

  it('opens version details from the version link', () => {
    render(<SkillHistory />, { wrapper: Wrapper });

    fireEvent.click(screen.getByRole('link', { name: 'v1' }));

    expect(screen.getByRole('dialog', { name: 'Summarize Findings' })).toBeInTheDocument();
    expect(screen.getByText('Older template')).toBeInTheDocument();
  });

  it('restores a non-current version by saving a new skill version', async () => {
    render(<SkillHistory />, { wrapper: Wrapper });

    fireEvent.click(screen.getAllByRole('button', { name: 'More actions' })[1]);
    fireEvent.click(screen.getByRole('menuitem', { name: /restore/i }));

    await waitFor(() => {
      expect(updateSkill).toHaveBeenCalledWith('skill1', {
        name: 'Summarize Findings',
        description: 'Older prompt',
        template: 'Older template',
        parameters: [{ name: 'limit', type: 'integer', description: 'Result limit', required: false, default: 10 }],
        triggers: ['summarize'],
        tools_required: ['graph__query'],
        enabled: false,
        comment: 'Restored from version 1',
      });
    });
    await waitFor(() => {
      expect(screen.getByTestId('nav-location')).toHaveTextContent('/app/skillsets/skillset1/skills');
    });
  });
});
