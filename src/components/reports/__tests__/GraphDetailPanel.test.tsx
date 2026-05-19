import { render, screen, cleanup, within } from '@testing-library/react';
import GraphDetailPanel, { GraphSummaryPanel } from '../GraphDetailPanel';

afterEach(cleanup);

describe('GraphDetailPanel', () => {
  it('renders node metadata separately from node properties', () => {
    render(
      <GraphDetailPanel
        type="node"
        data={{
          id: 'domain-alert-id',
          neo4j_id: 42,
          labels: ['GitHubDependabotAlert'],
          properties: {
            id: 'domain-alert-id',
            package_name: 'openssl',
          },
          label: 'Alert A',
          group: 'GitHubDependabotAlert',
        }}
      />,
    );

    expect(screen.getByText('Metadata')).toBeInTheDocument();
    expect(screen.getByText('Properties')).toBeInTheDocument();
    expect(screen.getAllByText('Key')).toHaveLength(2);
    expect(screen.getAllByText('Value')).toHaveLength(2);
    expect(screen.getByText('Neo4j ID')).toBeInTheDocument();
    expect(screen.getByText('42')).toBeInTheDocument();
    expect(screen.getByText('domain-alert-id')).toBeInTheDocument();
    expect(screen.getByText('openssl')).toBeInTheDocument();
    expect(screen.getByRole('list')).toBeInTheDocument();
    expect(
      within(screen.getByRole('list')).getByText('GitHubDependabotAlert'),
    ).toBeInTheDocument();
    expect(screen.queryByText('Additional Fields')).not.toBeInTheDocument();
  });

  it('renders relationship metadata separately from relationship properties', () => {
    render(
      <GraphDetailPanel
        type="link"
        data={{
          neo4j_id: 7,
          source: 42,
          target: 43,
          type: 'AFFECTS',
          properties: {
            id: 'domain-rel-id',
          },
        }}
      />,
    );

    expect(screen.getByText('Metadata')).toBeInTheDocument();
    expect(screen.getByText('Properties')).toBeInTheDocument();
    expect(screen.getByText('AFFECTS')).toBeInTheDocument();
    expect(screen.getByText('domain-rel-id')).toBeInTheDocument();
  });
});

describe('GraphSummaryPanel', () => {
  it('renders an empty overview instead of crashing when graph data is malformed', () => {
    expect(() =>
      render(
        <GraphSummaryPanel
          nodes={{ bad: 'shape' }}
          links={null}
          nodeGroupKey="group"
          getColor={() => '#8FB4FF'}
        />,
      ),
    ).not.toThrow();

    expect(screen.getByText('0 nodes')).toBeInTheDocument();
  });

  it('summarizes node groups and relationship types', () => {
    render(
      <GraphSummaryPanel
        nodes={[
          { id: 'a', group: 'CVE' },
          { id: 'b', properties: { group: 'Package' } },
        ]}
        links={[{ source: 'a', target: 'b', type: 'AFFECTS' }]}
        nodeGroupKey="group"
        getColor={() => '#8FB4FF'}
      />,
    );

    expect(screen.getByText('2 nodes')).toBeInTheDocument();
    expect(screen.getByText('CVE: 1')).toBeInTheDocument();
    expect(screen.getByText('Package: 1')).toBeInTheDocument();
    expect(screen.getByText('1 relationship')).toBeInTheDocument();
    expect(screen.getByText('→ AFFECTS: 1')).toBeInTheDocument();
  });
});
