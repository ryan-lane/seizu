import fc from 'fast-check';
import { buildBarDataset } from '../CypherBar';
import { buildPieData } from '../CypherPie';
import { calculateProgressPercent } from '../CypherProgress';
import { extractGraphData, computeLayout } from '../CypherGraph';
import { flattenRecord, formatValue } from '../CypherTable';

const safeKey = fc
  .string({ minLength: 1, maxLength: 12 })
  .filter((key) => /^[A-Za-z][A-Za-z0-9_]*$/.test(key));

const scalar = fc.oneof(
  fc.string({ maxLength: 30 }),
  fc.integer({ min: -10000, max: 10000 }),
  fc.boolean(),
  fc.constant(null),
  fc.constant(undefined),
);

const propertyValue = fc.oneof(scalar, fc.array(scalar, { maxLength: 5 }));

const chartProperties = fc
  .tuple(
    fc.oneof(
      fc.string({ maxLength: 24 }),
      fc.integer({ min: -10000, max: 10000 }),
      fc.constant(null),
      fc.constant(undefined),
    ),
    fc.oneof(
      fc.string({ maxLength: 24 }),
      fc.integer({ min: -10000, max: 10000 }),
      fc.constant(null),
      fc.constant(undefined),
    ),
    fc.dictionary(safeKey, propertyValue, { maxKeys: 8 }),
  )
  .map(([id, value, extra]) => ({ ...extra, id, value }));

const chartRecord = fc.oneof(
  chartProperties.map((properties) => ({ details: properties })),
  chartProperties.map((properties) => ({ details: { properties } })),
);

describe('Cypher-backed panel data fuzzing', () => {
  it('fuzzes bar chart records into chart-safe string or number fields', () => {
    fc.assert(
      fc.property(fc.array(chartRecord, { maxLength: 30 }), (records) => {
        const dataset = buildBarDataset(records);

        expect(dataset).toHaveLength(records.length);
        for (const row of dataset) {
          for (const value of Object.values(row)) {
            expect(['string', 'number']).toContain(typeof value);
          }
        }
      }),
      { numRuns: 100 },
    );
  });

  it('fuzzes pie chart records into finite values and stable labels', () => {
    fc.assert(
      fc.property(fc.array(chartRecord, { maxLength: 30 }), (records) => {
        const data = buildPieData(records);

        expect(data).toHaveLength(records.length);
        for (const item of data) {
          expect(typeof item.id).toBe('string');
          expect(item.label).toBe(item.id);
          expect(Number.isFinite(item.value)).toBe(true);
        }
      }),
      { numRuns: 100 },
    );
  });

  it('fuzzes progress panel percentages for finite count pairs', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 0, max: 1_000_000 }),
        fc.integer({ min: 0, max: 1_000_000 }),
        (numerator, denominator) => {
          const percent = calculateProgressPercent(numerator, denominator);

          expect(Number.isFinite(percent)).toBe(true);
          expect(percent).toBe(
            denominator === 0 ? 0 : Math.floor((numerator / denominator) * 100),
          );
        },
      ),
      { numRuns: 100 },
    );
  });

  it('fuzzes table flattening and display formatting for Neo4j-like values', () => {
    const nodeRecord = fc
      .dictionary(safeKey, propertyValue, { minKeys: 1, maxKeys: 8 })
      .map((properties) => ({
        n: {
          id: properties.id ?? 'neo4j-id',
          labels: ['Node'],
          properties,
        },
      }));

    fc.assert(
      fc.property(nodeRecord, (record) => {
        const flattened = flattenRecord(record);

        expect(flattened).toBe(record.n.properties);
        for (const value of Object.values(flattened)) {
          expect(typeof formatValue(value)).toBe('string');
        }
      }),
      { numRuns: 100 },
    );
  });

  it('fuzzes graph path extraction and layout with Cypher path-shaped records', () => {
    const graphPath = fc
      .array(
        fc.record({
          id: fc.integer({ min: 1, max: 1000 }),
          name: fc.string({ minLength: 1, maxLength: 20 }),
          group: fc.string({ minLength: 1, maxLength: 12 }),
        }),
        { minLength: 1, maxLength: 12 },
      )
      .map((items) => {
        const deduped = [
          ...new Map(items.map((item) => [item.id, item])).values(),
        ];
        const nodes = deduped.map((item) => ({
          id: item.id,
          labels: [item.group],
          properties: { id: `node-${item.id}`, name: item.name },
        }));
        const relationships = nodes.slice(1).map((node, index) => ({
          id: index + 1,
          type: 'RELATED_TO',
          start_node_id: nodes[index].id,
          end_node_id: node.id,
          properties: {},
        }));
        return [{ path: { nodes, relationships } }];
      });

    fc.assert(
      fc.property(graphPath, (records) => {
        const graph = extractGraphData(records, 'name');

        expect(graph).not.toBeNull();
        const nodeIds = new Set(graph!.nodes.map((node) => String(node.id)));
        expect(nodeIds.size).toBe(graph!.nodes.length);
        for (const link of graph!.links) {
          expect(nodeIds.has(String(link.source))).toBe(true);
          expect(nodeIds.has(String(link.target))).toBe(true);
        }

        const positions = computeLayout(
          graph!.nodes,
          graph!.links,
          800,
          450,
          1,
        );
        expect(positions.size).toBe(graph!.nodes.length);
        for (const position of positions.values()) {
          expect(Number.isFinite(position.x)).toBe(true);
          expect(Number.isFinite(position.y)).toBe(true);
        }
      }),
      { numRuns: 50 },
    );
  });
});
