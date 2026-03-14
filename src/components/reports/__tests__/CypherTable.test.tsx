import { render, screen } from '@testing-library/react';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CypherTable from '../CypherTable';

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

describe('CypherTable', () => {
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
        <CypherTable />
      </Wrapper>
    );
    expect(screen.getByText('Missing cypher query')).toBeInTheDocument();
  });

  it('shows needInputs message when needInputs is provided', () => {
    useLazyCypherQuery.mockReturnValue([
      mockRunQuery,
      { loading: false, error: null, records: [], first: undefined }
    ]);
    render(
      <Wrapper>
        <CypherTable
          cypher="MATCH (n) RETURN n"
          needInputs={['environment', 'team']}
        />
      </Wrapper>
    );
    expect(
      screen.getByText(/please set environment, team/i)
    ).toBeInTheDocument();
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
        <CypherTable cypher="MATCH (n) RETURN n" />
      </Wrapper>
    );
    expect(
      screen.getByText(/failed to load requested data/i)
    ).toBeInTheDocument();
  });

  it('shows no records message when records array is empty', () => {
    useLazyCypherQuery.mockReturnValue([
      mockRunQuery,
      { loading: false, error: null, records: [], first: undefined }
    ]);
    render(
      <Wrapper>
        <CypherTable cypher="MATCH (n) RETURN n" />
      </Wrapper>
    );
    expect(screen.getByText('No records found.')).toBeInTheDocument();
  });

  it('renders a caption when data is loaded', () => {
    const mockRecord = { name: 'test' };
    useLazyCypherQuery.mockReturnValue([
      mockRunQuery,
      {
        loading: false,
        error: null,
        records: [mockRecord],
        first: mockRecord
      }
    ]);
    render(
      <Wrapper>
        <CypherTable
          cypher="MATCH (n) RETURN n"
          caption="My Table"
          columns={[{ name: 'name', label: 'Name' }]}
        />
      </Wrapper>
    );
    expect(screen.getByText('My Table')).toBeInTheDocument();
  });
});
