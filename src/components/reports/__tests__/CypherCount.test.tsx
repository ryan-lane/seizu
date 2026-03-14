import { render, screen } from '@testing-library/react';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CypherCount from '../CypherCount';

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

describe('CypherCount', () => {
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
        <CypherCount caption="Test Count" />
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
        <CypherCount
          cypher="MATCH (n) RETURN count(n) as total"
          caption="Test Count"
          needInputs={['param1', 'param2']}
        />
      </Wrapper>
    );
    expect(screen.getByText('N/A')).toBeInTheDocument();
    expect(screen.getByText('(Set param1, param2)')).toBeInTheDocument();
  });

  it('shows loading spinner when loading', () => {
    useLazyCypherQuery.mockReturnValue([
      mockRunQuery,
      { loading: true, error: null, records: undefined, first: undefined }
    ]);
    const { container } = render(
      <Wrapper>
        <CypherCount
          cypher="MATCH (n) RETURN count(n) as total"
          caption="Test Count"
        />
      </Wrapper>
    );
    // ThreeDots spinner is rendered
    expect(container.firstChild).not.toBeNull();
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
        <CypherCount
          cypher="MATCH (n) RETURN count(n) as total"
          caption="Test Count"
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
        <CypherCount
          cypher="MATCH (n) RETURN count(n) as total"
          caption="Test Count"
        />
      </Wrapper>
    );
    expect(screen.getByText('N/A')).toBeInTheDocument();
  });

  it('renders the count value when data is loaded', () => {
    useLazyCypherQuery.mockReturnValue([
      mockRunQuery,
      {
        loading: false,
        error: null,
        records: [{ total: 42 }],
        first: { total: 42 }
      }
    ]);
    render(
      <Wrapper>
        <CypherCount
          cypher="MATCH (n) RETURN count(n) as total"
          caption="Test Count"
        />
      </Wrapper>
    );
    expect(screen.getByText('Test Count')).toBeInTheDocument();
    expect(screen.getByText('42')).toBeInTheDocument();
  });
});
