import { render, screen } from '@testing-library/react';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CypherProgress from '../CypherProgress';

jest.mock('src/hooks/useCypherQuery', () => ({
  useLazyCypherQuery: jest.fn()
}));

jest.mock(
  'src/components/reports/CypherDetails',
  () =>
    function MockCypherDetails() {
      return null;
    }
);

const { useLazyCypherQuery } = require('src/hooks/useCypherQuery');

const theme = createTheme();

function Wrapper({ children }) {
  return <ThemeProvider theme={theme}>{children}</ThemeProvider>;
}

describe('CypherProgress', () => {
  const mockRunQuery = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    useLazyCypherQuery.mockReturnValue([
      mockRunQuery,
      { loading: false, error: null, records: undefined, first: undefined }
    ]);
  });

  it('shows error when cypher is undefined', () => {
    render(
      <Wrapper>
        <CypherProgress caption="Test Progress" />
      </Wrapper>
    );
    expect(screen.getByText('Missing cypher query')).toBeInTheDocument();
  });

  it('shows N/A with needInputs message when needInputs is provided', () => {
    useLazyCypherQuery.mockReturnValue([
      mockRunQuery,
      { loading: false, error: null, records: [], first: undefined }
    ]);
    render(
      <Wrapper>
        <CypherProgress
          cypher="MATCH (n) RETURN count(n) as numerator, count(n) as denominator"
          caption="Test Progress"
          needInputs={['team']}
        />
      </Wrapper>
    );
    expect(screen.getByText('N/A')).toBeInTheDocument();
    expect(screen.getByText('(Set team)')).toBeInTheDocument();
  });

  it('shows error message when query fails', () => {
    useLazyCypherQuery.mockReturnValue([
      mockRunQuery,
      {
        loading: false,
        error: new Error('Query failed'),
        records: undefined,
        first: undefined
      }
    ]);
    render(
      <Wrapper>
        <CypherProgress
          cypher="MATCH (n) RETURN count(n) as numerator, count(n) as denominator"
          caption="Test Progress"
        />
      </Wrapper>
    );
    expect(
      screen.getByText(/failed to load requested data/i)
    ).toBeInTheDocument();
  });

  it('shows N/A when records exist but first is undefined', () => {
    useLazyCypherQuery.mockReturnValue([
      mockRunQuery,
      { loading: false, error: null, records: [], first: undefined }
    ]);
    render(
      <Wrapper>
        <CypherProgress
          cypher="MATCH (n) RETURN count(n) as numerator, count(n) as denominator"
          caption="Test Progress"
        />
      </Wrapper>
    );
    expect(screen.getByText('N/A')).toBeInTheDocument();
  });

  it('renders circular progress when data is loaded', () => {
    useLazyCypherQuery.mockReturnValue([
      mockRunQuery,
      {
        loading: false,
        error: null,
        records: [{ numerator: 75, denominator: 100 }],
        first: { numerator: 75, denominator: 100 }
      }
    ]);
    render(
      <Wrapper>
        <CypherProgress
          cypher="MATCH (n) RETURN count(n) as numerator, count(n) as denominator"
          caption="Progress Caption"
        />
      </Wrapper>
    );
    expect(screen.getByText('Progress Caption')).toBeInTheDocument();
    expect(screen.getByText('75%')).toBeInTheDocument();
  });
});
