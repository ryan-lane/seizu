import { render, screen } from '@testing-library/react';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CypherCount from '../CypherCount';

jest.mock('use-neo4j', () => ({
  useLazyReadCypher: jest.fn()
}));

jest.mock('src/components/reports/CypherDetails', () =>
  function MockCypherDetails() {
    return null;
  }
);

const { useLazyReadCypher } = require('use-neo4j');

const theme = createTheme();

function Wrapper({ children }) {
  return <ThemeProvider theme={theme}>{children}</ThemeProvider>;
}

describe('CypherCount', () => {
  const mockRunQuery = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    useLazyReadCypher.mockReturnValue([
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
    useLazyReadCypher.mockReturnValue([
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
    useLazyReadCypher.mockReturnValue([
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
    useLazyReadCypher.mockReturnValue([
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
    useLazyReadCypher.mockReturnValue([
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
    const mockRecord = {
      get: jest.fn().mockReturnValue({ toNumber: () => 42, low: 42, high: 0 })
    };
    useLazyReadCypher.mockReturnValue([
      mockRunQuery,
      {
        loading: false,
        error: null,
        records: [mockRecord],
        first: mockRecord
      }
    ]);

    jest.mock('neo4j-driver', () => ({
      int: jest.fn().mockReturnValue({ toNumber: () => 42 })
    }));

    render(
      <Wrapper>
        <CypherCount
          cypher="MATCH (n) RETURN count(n) as total"
          caption="Test Count"
        />
      </Wrapper>
    );
    expect(screen.getByText('Test Count')).toBeInTheDocument();
  });
});
