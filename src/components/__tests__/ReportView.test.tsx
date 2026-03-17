/**
 * Tests for the params-building logic in ReportView.
 *
 * The key regression: when a panel param has `input_id` but no `value` key
 * (because _strip_none removed the null value when storing in DynamoDB), the
 * old code used `!== null` which treated `undefined` as "value is set", causing
 * params to be sent as `{}` and triggering Neo4j ParameterMissing errors.
 * The fix uses `!= null` (loose) which handles both null and undefined.
 */
import { render, cleanup } from '@testing-library/react';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import ReportView from 'src/components/ReportView';
import { Report } from 'src/config.context';

// ---------------------------------------------------------------------------
// Mock all panel components to capture their props
// ---------------------------------------------------------------------------

let lastCountProps: Record<string, unknown> = {};
let lastProgressProps: Record<string, unknown> = {};
let lastTableProps: Record<string, unknown> = {};

jest.mock('src/components/reports/CypherCount', () => ({
  __esModule: true,
  default: function MockCount(props: Record<string, unknown>) {
    lastCountProps = props;
    return null;
  }
}));

jest.mock('src/components/reports/CypherProgress', () => ({
  __esModule: true,
  default: function MockProgress(props: Record<string, unknown>) {
    lastProgressProps = props;
    return null;
  }
}));

jest.mock('src/components/reports/CypherTable', () => ({
  __esModule: true,
  default: function MockTable(props: Record<string, unknown>) {
    lastTableProps = props;
    return null;
  }
}));

jest.mock('src/components/reports/CypherPie', () => ({
  __esModule: true,
  default: () => null
}));

jest.mock('src/components/reports/CypherBar', () => ({
  __esModule: true,
  default: () => null
}));

jest.mock('src/components/reports/CypherVerticalTable', () => ({
  __esModule: true,
  default: () => null
}));

jest.mock('src/components/reports/CypherAutocomplete', () => ({
  __esModule: true,
  default: () => null
}));

jest.mock('src/components/reports/FreeTextInput', () => ({
  __esModule: true,
  default: () => null
}));

jest.mock('src/components/QueryString', () => ({
  getQueryStringValue: () => undefined
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const theme = createTheme();
function Wrapper({ children }: { children: React.ReactNode }) {
  return <ThemeProvider theme={theme}>{children}</ThemeProvider>;
}

const QUERIES: Record<string, string> = {
  'cves-total': 'MATCH (c:CVE) RETURN count(c.id) AS total',
  'cves-severity': 'MATCH (c:CVE) WHERE c.base_severity = $base_severity RETURN count(c) AS total',
  'cves-list': 'MATCH (c:CVE) WHERE c.base_severity =~ ($base_severity) RETURN c'
};

function makeReport(panels: Report['rows'][0]['panels'], queries?: Record<string, string>): Report {
  return {
    name: 'Test',
    queries: queries ?? QUERIES,
    inputs: [
      {
        input_id: 'cve_severity',
        type: 'autocomplete',
        label: 'Base Severity',
        cypher: 'MATCH (c:CVE) RETURN DISTINCT c.base_severity AS value'
      }
    ],
    rows: [{ name: 'Row 1', panels }]
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('ReportView param building', () => {
  beforeEach(() => {
    lastCountProps = {};
    lastProgressProps = {};
    lastTableProps = {};
  });

  afterEach(cleanup);

  it('passes static value params correctly to panel', () => {
    const report = makeReport([
      {
        type: 'count',
        cypher: 'cves-severity',
        caption: 'Critical CVEs',
        params: [{ name: 'base_severity', value: 'CRITICAL' }]
      }
    ]);

    render(
      <Wrapper>
        <ReportView report={report} title="Test" />
      </Wrapper>
    );

    expect(lastCountProps.params).toEqual({ base_severity: 'CRITICAL' });
    expect(lastCountProps.needInputs).toEqual([]);
  });

  it('adds to needInputs when value key is absent (as after DynamoDB _strip_none)', () => {
    // Regression: value key absent (undefined) should not be treated as "value is set".
    // This simulates a param stored in DynamoDB where input_id was set and value was null,
    // so _strip_none removed the value key entirely — the object only has {name, input_id}.
    const report = makeReport([
      {
        type: 'count',
        cypher: 'cves-list',
        caption: 'CVE Table',
        params: [{ name: 'base_severity', input_id: 'cve_severity' }]
      }
    ]);

    render(
      <Wrapper>
        <ReportView report={report} title="Test" />
      </Wrapper>
    );

    // No value in varData yet → should add the input label to needInputs
    expect(lastCountProps.needInputs).toEqual(['Base Severity']);
    // params dict should NOT contain base_severity set to undefined
    expect((lastCountProps.params as Record<string, unknown>)['base_severity']).toBeUndefined();
  });

  it('adds to needInputs when value is explicitly null (original YAML-loaded behavior)', () => {
    // Before DynamoDB: Pydantic model_dump() included value: null in JSON.
    // The null value should also fall through to the input_id branch.
    const report = makeReport([
      {
        type: 'count',
        cypher: 'cves-list',
        caption: 'CVE Table',
        params: [{ name: 'base_severity', value: null as unknown as string, input_id: 'cve_severity' }]
      }
    ]);

    render(
      <Wrapper>
        <ReportView report={report} title="Test" />
      </Wrapper>
    );

    expect(lastCountProps.needInputs).toEqual(['Base Severity']);
  });

  it('passes params correctly for progress panel with static value', () => {
    const report = makeReport([
      {
        type: 'progress',
        cypher: 'cves-severity',
        caption: 'Critical CVEs',
        threshold: 0,
        params: [{ name: 'base_severity', value: 'CRITICAL' }]
      }
    ]);

    render(
      <Wrapper>
        <ReportView report={report} title="Test" />
      </Wrapper>
    );

    expect(lastProgressProps.params).toEqual({ base_severity: 'CRITICAL' });
    expect(lastProgressProps.needInputs).toEqual([]);
  });

  it('passes empty params when panel has no params defined', () => {
    const report = makeReport([
      {
        type: 'count',
        cypher: 'cves-total',
        caption: 'Total CVEs'
      }
    ]);

    render(
      <Wrapper>
        <ReportView report={report} title="Test" />
      </Wrapper>
    );

    expect(lastCountProps.params).toEqual({});
    expect(lastCountProps.needInputs).toEqual([]);
  });

  it('passes multiple static params to panel', () => {
    const report = makeReport([
      {
        type: 'count',
        cypher: 'cves-severity',
        caption: 'CVEs',
        params: [
          { name: 'base_severity', value: 'HIGH' },
          { name: 'limit', value: '10' }
        ]
      }
    ]);

    render(
      <Wrapper>
        <ReportView report={report} title="Test" />
      </Wrapper>
    );

    expect(lastCountProps.params).toEqual({ base_severity: 'HIGH', limit: '10' });
  });

  it('resolves named query reference from report.queries', () => {
    const report = makeReport([
      {
        type: 'count',
        cypher: 'cves-total',
        caption: 'Total CVEs'
      }
    ]);

    render(
      <Wrapper>
        <ReportView report={report} title="Test" />
      </Wrapper>
    );

    expect(lastCountProps.cypher).toBe('MATCH (c:CVE) RETURN count(c.id) AS total');
  });

  it('passes direct Cypher string to panel when not found in report.queries', () => {
    const directCypher = 'MATCH (c:CVE) RETURN count(c.id) AS total';
    const report = makeReport(
      [
        {
          type: 'count',
          cypher: directCypher,
          caption: 'Total CVEs (direct)'
        }
      ],
      {} // empty queries dict — no named references
    );

    render(
      <Wrapper>
        <ReportView report={report} title="Test" />
      </Wrapper>
    );

    // The literal Cypher string should be passed through unchanged
    expect(lastCountProps.cypher).toBe(directCypher);
  });

  it('falls back to literal string when panel.cypher is not in report.queries', () => {
    const directCypher = 'MATCH (n) RETURN count(n) AS total';
    const report = makeReport([
      {
        type: 'count',
        cypher: directCypher,
        caption: 'All Nodes'
      }
    ]);
    // QUERIES does not contain directCypher as a key, so it should be used as-is

    render(
      <Wrapper>
        <ReportView report={report} title="Test" />
      </Wrapper>
    );

    expect(lastCountProps.cypher).toBe(directCypher);
  });
});
