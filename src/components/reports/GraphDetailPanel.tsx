import {
  Box,
  Divider,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import type { GraphNode, GraphLink } from 'src/components/reports/CypherGraph';

// XyFlow internal node properties — exclude from display.
export const GRAPH_INTERNAL_PROPS = new Set([
  'x', 'y', 'vx', 'vy', 'fx', 'fy', '__indexColor', 'index',
  // XyFlow node-data keys we add internally
  'original', 'label', 'group',
]);

// ─── Item detail panel ────────────────────────────────────────────────────────

interface GraphDetailPanelProps {
  type: 'node' | 'link';
  data: GraphNode | GraphLink;
}

type DetailEntry = [string, unknown];

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function detailValue(value: unknown): string {
  if (typeof value === 'object' && value !== null) return JSON.stringify(value);
  return String(value ?? '');
}

function DetailValue({ value }: { value: unknown }) {
  if (Array.isArray(value)) {
    return (
      <Box component="ul" sx={{ m: 0, pl: 2.25 }}>
        {value.map((item, index) => (
          <Box component="li" key={index} sx={{ mb: 0.25 }}>
            <Typography variant="body2" sx={{ wordBreak: 'break-all' }}>
              {detailValue(item)}
            </Typography>
          </Box>
        ))}
      </Box>
    );
  }

  return (
    <Typography variant="body2" sx={{ wordBreak: 'break-all' }}>
      {detailValue(value)}
    </Typography>
  );
}

function displayKey(key: string): string {
  switch (key) {
    case 'neo4j_id':
      return 'Neo4j ID';
    case 'start_node_id':
      return 'Source Neo4j ID';
    case 'end_node_id':
      return 'Target Neo4j ID';
    default:
      return key;
  }
}

function readGraphValue(item: GraphNode | GraphLink, key: string): unknown {
  const properties = item.properties;
  if (key !== 'group' && properties && Object.prototype.hasOwnProperty.call(properties, key)) {
    return properties[key];
  }
  if (Object.prototype.hasOwnProperty.call(item, key)) {
    return item[key];
  }
  return properties?.[key];
}

function DetailSection({
  title,
  entries,
  emptyText,
  formatMetadataKeys = false,
}: {
  title: string;
  entries: DetailEntry[];
  emptyText?: string;
  formatMetadataKeys?: boolean;
}) {
  if (entries.length === 0 && !emptyText) return null;

  return (
    <Box sx={{ mb: 2 }}>
      <Typography variant="subtitle2" gutterBottom>
        {title}
      </Typography>
      {entries.length === 0 ? (
        <Typography variant="body2" color="text.secondary">
          {emptyText}
        </Typography>
      ) : (
        <TableContainer>
          <Table
            size="small"
            aria-label={`${title} details`}
            sx={{
              tableLayout: 'fixed',
              '& th, & td': {
                borderColor: 'divider',
                px: 0.75,
                py: 0.625,
                verticalAlign: 'top',
              },
            }}
          >
            <TableHead>
              <TableRow>
                <TableCell sx={{ width: '38%' }}>
                  <Typography variant="caption" color="text.secondary">
                    Key
                  </Typography>
                </TableCell>
                <TableCell>
                  <Typography variant="caption" color="text.secondary">
                    Value
                  </Typography>
                </TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {entries.map(([k, v]) => (
                <TableRow key={k}>
                  <TableCell>
                    <Typography variant="caption" color="text.secondary" sx={{ wordBreak: 'break-word' }}>
                      {formatMetadataKeys ? displayKey(k) : k}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <DetailValue value={v} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </Box>
  );
}

function metadataEntries(type: 'node' | 'link', data: GraphNode | GraphLink): DetailEntry[] {
  if (type === 'node') {
    const node = data as GraphNode;
    return [
      ...(node.neo4j_id !== undefined ? [['neo4j_id', node.neo4j_id] as DetailEntry] : [['id', node.id] as DetailEntry]),
      ...(node.labels ? [['labels', node.labels] as DetailEntry] : []),
    ];
  }

  const link = data as GraphLink;
  return [
    ...(link.neo4j_id !== undefined
      ? [['neo4j_id', link.neo4j_id] as DetailEntry]
      : link.id !== undefined
        ? [['id', link.id] as DetailEntry]
        : []),
    ...(link.type !== undefined ? [['type', link.type] as DetailEntry] : []),
    ['source', typeof link.source === 'object' ? link.source.id : link.source],
    ['target', typeof link.target === 'object' ? link.target.id : link.target],
  ];
}

export default function GraphDetailPanel({ type, data }: GraphDetailPanelProps) {
  const nestedProperties = isRecord(data.properties) ? data.properties : null;
  const metadataKeys = new Set(['id', 'neo4j_id', 'labels', 'source', 'target', 'type', 'properties']);
  const additionalEntries = Object.entries(data).filter(
    ([k]) => !metadataKeys.has(k) && !GRAPH_INTERNAL_PROPS.has(k),
  );
  const propertyEntries = nestedProperties ? Object.entries(nestedProperties) : additionalEntries;
  const otherEntries = nestedProperties ? additionalEntries : [];

  return (
    <Box>
      <Typography variant="overline" color="text.secondary" display="block" gutterBottom>
        {type === 'node' ? 'Node' : 'Relationship'}
      </Typography>
      <DetailSection title="Metadata" entries={metadataEntries(type, data)} formatMetadataKeys />
      <DetailSection title="Properties" entries={propertyEntries} emptyText="No properties" />
      <DetailSection title="Additional Fields" entries={otherEntries} />
    </Box>
  );
}

// ─── Graph summary panel ──────────────────────────────────────────────────────

interface GraphSummaryPanelProps {
  nodes: GraphNode[];
  links: GraphLink[];
  nodeGroupKey: string;
  getColor: (group: string) => string;
}

export function GraphSummaryPanel({ nodes, links, nodeGroupKey, getColor }: GraphSummaryPanelProps) {
  const groupCounts = new Map<string, number>();
  nodes.forEach(n => {
    const g = String(readGraphValue(n, nodeGroupKey) ?? 'default');
    groupCounts.set(g, (groupCounts.get(g) ?? 0) + 1);
  });

  const typeCounts = new Map<string, number>();
  links.forEach(l => {
    const t = l.type ? String(l.type) : null;
    if (t) typeCounts.set(t, (typeCounts.get(t) ?? 0) + 1);
  });

  return (
    <Box>
      <Typography variant="overline" color="text.secondary" display="block" gutterBottom>
        Graph Overview
      </Typography>

      <Typography variant="body2" gutterBottom>
        {nodes.length} {nodes.length === 1 ? 'node' : 'nodes'}
      </Typography>
      {[...groupCounts.entries()].map(([group, count]) => (
        <Box key={group} sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5, pl: 1 }}>
          <Box
            sx={{
              width: 10,
              height: 10,
              borderRadius: '50%',
              bgcolor: getColor(group),
              flexShrink: 0,
            }}
          />
          <Typography variant="caption" color="text.secondary">
            {group}: {count}
          </Typography>
        </Box>
      ))}

      {links.length > 0 && (
        <>
          <Divider sx={{ my: 1.5 }} />
          <Typography variant="body2" gutterBottom>
            {links.length} {links.length === 1 ? 'relationship' : 'relationships'}
          </Typography>
          {typeCounts.size > 0
            ? [...typeCounts.entries()].map(([type, count]) => (
                <Box key={type} sx={{ pl: 1, mb: 0.5 }}>
                  <Typography variant="caption" color="text.secondary">
                    → {type}: {count}
                  </Typography>
                </Box>
              ))
            : null}
        </>
      )}
    </Box>
  );
}
