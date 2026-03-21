import { useEffect, useMemo, useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  CardHeader,
  Divider,
  Grid,
  IconButton,
  Tab,
  Tabs,
  Tooltip,
  Typography
} from '@mui/material';
import CypherTable from 'src/components/reports/CypherTable';
import { useTheme } from '@mui/material/styles';
import InfoOutlined from '@mui/icons-material/InfoOutlined';
import Info from '@mui/icons-material/Info';
import Error from '@mui/icons-material/Error';
import { ThreeDots } from 'react-loader-spinner';
import {
  ReactFlow,
  Background,
  BackgroundVariant,
  Controls,
  Edge,
  Handle,
  MarkerType,
  Node,
  NodeProps,
  Position,
  useEdgesState,
  useNodesState,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { useLazyCypherQuery } from 'src/hooks/useCypherQuery';
import QueryValidationBadge from 'src/components/reports/QueryValidationBadge';
import GraphDetailPanel, { GraphSummaryPanel } from 'src/components/reports/GraphDetailPanel';

interface GraphSettings {
  node_label?: string;
  node_color_by?: string;
}

export interface GraphNode {
  id: string | number;
  label?: string;
  group?: string;
  [key: string]: unknown;
}

export interface GraphLink {
  source: string | number | GraphNode;
  target: string | number | GraphNode;
  type?: string;
  [key: string]: unknown;
}

interface GraphData {
  nodes: GraphNode[];
  links: GraphLink[];
}

// ─── Neo4j path format ────────────────────────────────────────────────────────

interface Neo4jPathNode {
  id: string | number;
  labels: string[];
  properties: Record<string, unknown>;
}

interface Neo4jPathRelationship {
  id: string | number;
  type: string;
  start_node_id: string | number;
  end_node_id: string | number;
  properties: Record<string, unknown>;
}

interface Neo4jPathValue {
  nodes: Neo4jPathNode[];
  relationships: Neo4jPathRelationship[];
}

function isPathValue(v: unknown): v is Neo4jPathValue {
  if (typeof v !== 'object' || v === null) return false;
  const obj = v as Record<string, unknown>;
  return Array.isArray(obj['nodes']) && Array.isArray(obj['relationships']);
}

/**
 * Given query records, extract a GraphData object.
 *
 * Tries two formats in order:
 *  1. Explicit graph key: first record has a `graph` key with `{nodes, links}` arrays.
 *  2. Path format: any value in any record that has `{nodes, relationships}` — the
 *     backend serialises Neo4j Path objects this way when the query does `RETURN path`.
 *     Nodes are de-duplicated by id across all records.
 */
function extractGraphData(
  records: Record<string, unknown>[],
  nodeLabelKey: string,
): GraphData | null {
  if (records.length === 0) return null;

  // ── Format 1: explicit graph map (any key whose value has {nodes, links}) ─
  for (const value of Object.values(records[0])) {
    const v = value as GraphData | undefined;
    if (v && Array.isArray(v.nodes) && Array.isArray(v.links)) {
      return v;
    }
  }

  // ── Format 2: path values across all records ──────────────────────────────
  const nodeMap = new Map<string | number, GraphNode>();
  const links: GraphLink[] = [];
  let foundPaths = false;

  for (const record of records) {
    for (const value of Object.values(record)) {
      if (!isPathValue(value)) continue;
      foundPaths = true;
      for (const n of value.nodes) {
        if (!nodeMap.has(n.id)) {
          nodeMap.set(n.id, {
            ...n.properties,
            id: n.id,
            label: String(n.properties[nodeLabelKey] ?? n.properties['name'] ?? n.id),
            group: n.labels[0] ?? 'default',
          });
        }
      }
      for (const rel of value.relationships) {
        links.push({
          ...rel.properties,
          source: rel.start_node_id,
          target: rel.end_node_id,
          type: rel.type,
        });
      }
    }
  }

  if (foundPaths) {
    return { nodes: [...nodeMap.values()], links };
  }

  return null;
}

interface CypherGraphProps {
  cypher?: string;
  params?: Record<string, unknown>;
  caption?: string;
  graphSettings?: GraphSettings;
  needInputs?: string[];
  /** Whether the details panel starts open. Default false (collapsed). */
  defaultDetailOpen?: boolean;
}

// ─── Colours ─────────────────────────────────────────────────────────────────

const PALETTE = [
  '#02B2AF', '#2E96FF', '#B800D8', '#60009B',
  '#2731C8', '#03008D', '#00B929', '#FF5733',
  '#FFA500', '#E91E63',
];

const GROUP_COLOR_MAP = new Map<string, string>();

export function colorForGroup(group: string): string {
  if (!GROUP_COLOR_MAP.has(group)) {
    GROUP_COLOR_MAP.set(group, PALETTE[GROUP_COLOR_MAP.size % PALETTE.length]);
  }
  return GROUP_COLOR_MAP.get(group)!;
}

// ─── Force layout ─────────────────────────────────────────────────────────────

function computeLayout(
  nodes: GraphNode[],
  links: GraphLink[],
  width: number,
  height: number,
): Map<string, { x: number; y: number }> {
  if (nodes.length === 0) return new Map();

  const SPRING_LEN = 140;
  const SPRING_K = 0.06;
  const REPULSION = 3000;
  const DAMPING = 0.82;

  const positions = new Map<string, { x: number; y: number; vx: number; vy: number }>();
  const cx = width / 2;
  const cy = height / 2;
  const r = Math.min(width, height) * 0.32;
  nodes.forEach((n, i) => {
    const angle = (i / Math.max(nodes.length, 1)) * 2 * Math.PI;
    positions.set(String(n.id), {
      x: cx + r * Math.cos(angle),
      y: cy + r * Math.sin(angle),
      vx: 0,
      vy: 0,
    });
  });

  const nodeIds = nodes.map(n => String(n.id));
  const edgePairs = links.map(l => ({
    source: String(typeof l.source === 'object' ? (l.source as GraphNode).id : l.source),
    target: String(typeof l.target === 'object' ? (l.target as GraphNode).id : l.target),
  }));

  for (let iter = 0; iter < 150; iter++) {
    const alpha = 1 - iter / 150;

    nodeIds.forEach(id => {
      const p = positions.get(id)!;
      p.vx = 0;
      p.vy = 0;
    });

    for (let i = 0; i < nodeIds.length; i++) {
      for (let j = i + 1; j < nodeIds.length; j++) {
        const a = positions.get(nodeIds[i])!;
        const b = positions.get(nodeIds[j])!;
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const d2 = Math.max(dx * dx + dy * dy, 1);
        const d = Math.sqrt(d2);
        const f = (REPULSION * alpha) / d2;
        a.vx -= (dx / d) * f;
        a.vy -= (dy / d) * f;
        b.vx += (dx / d) * f;
        b.vy += (dy / d) * f;
      }
    }

    edgePairs.forEach(({ source, target }) => {
      const a = positions.get(source);
      const b = positions.get(target);
      if (!a || !b) return;
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      const d = Math.max(Math.sqrt(dx * dx + dy * dy), 1);
      const f = SPRING_K * (d - SPRING_LEN) * alpha;
      a.vx += (dx / d) * f;
      a.vy += (dy / d) * f;
      b.vx -= (dx / d) * f;
      b.vy -= (dy / d) * f;
    });

    nodeIds.forEach(id => {
      const p = positions.get(id)!;
      p.x += p.vx * DAMPING;
      p.y += p.vy * DAMPING;
    });
  }

  const result = new Map<string, { x: number; y: number }>();
  positions.forEach((p, id) => result.set(id, { x: p.x, y: p.y }));
  return result;
}

// ─── Custom node ──────────────────────────────────────────────────────────────

function GraphNodeComponent({ data, selected }: NodeProps) {
  const theme = useTheme();
  const color = colorForGroup(String(data['group'] ?? 'default'));
  const label = String(data['label'] ?? data['id'] ?? '');

  return (
    <div style={{ textAlign: 'center', cursor: 'pointer' }}>
      <Handle type="target" position={Position.Top} style={{ opacity: 0, width: 0, height: 0, minWidth: 0, minHeight: 0 }} />
      <div
        style={{
          width: 30,
          height: 30,
          borderRadius: '50%',
          background: color,
          border: `2.5px solid ${selected ? theme.palette.primary.main : theme.palette.background.paper}`,
          boxSizing: 'border-box',
          margin: '0 auto',
          boxShadow: selected ? `0 0 0 2px ${theme.palette.primary.main}` : 'none',
        }}
      />
      <Handle type="source" position={Position.Bottom} style={{ opacity: 0, width: 0, height: 0, minWidth: 0, minHeight: 0 }} />
      <div
        style={{
          marginTop: 3,
          fontSize: 10,
          color: theme.palette.text.secondary,
          fontFamily: theme.typography.fontFamily ?? 'sans-serif',
          maxWidth: 80,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}
      >
        {label}
      </div>
    </div>
  );
}

const nodeTypes = { graphNode: GraphNodeComponent };

// ─── Converters ───────────────────────────────────────────────────────────────

function buildXyNodes(
  graphNodes: GraphNode[],
  positions: Map<string, { x: number; y: number }>,
  nodeLabelKey: string,
  nodeColorByKey: string,
): Node[] {
  return graphNodes.map(n => {
    const pos = positions.get(String(n.id)) ?? { x: 0, y: 0 };
    return {
      id: String(n.id),
      type: 'graphNode',
      position: pos,
      data: {
        ...n,
        label: String(n[nodeLabelKey] ?? n.id ?? ''),
        group: String(n[nodeColorByKey] ?? 'default'),
        original: n,
      },
    };
  });
}

function buildXyEdges(graphLinks: GraphLink[], edgeColor: string): Edge[] {
  return graphLinks.map((l, i) => {
    const source = String(typeof l.source === 'object' ? (l.source as GraphNode).id : l.source);
    const target = String(typeof l.target === 'object' ? (l.target as GraphNode).id : l.target);
    return {
      id: `edge-${i}`,
      source,
      target,
      label: l.type ?? undefined,
      labelStyle: { fontSize: 10 },
      style: { stroke: edgeColor, strokeWidth: 1.5 },
      markerEnd: { type: MarkerType.ArrowClosed, color: edgeColor },
      data: { original: l },
    };
  });
}

// ─── Main component ───────────────────────────────────────────────────────────

const DETAIL_PANEL_WIDTH = 280;

export default function CypherGraph({
  cypher,
  params,
  caption,
  graphSettings,
  needInputs,
  defaultDetailOpen = false,
}: CypherGraphProps) {
  const theme = useTheme();

  const [runQuery, { loading, error, records, warnings, queryErrors }] =
    useLazyCypherQuery(cypher);

  const [selectedItem, setSelectedItem] = useState<
    { type: 'node'; data: GraphNode } | { type: 'link'; data: GraphLink } | null
  >(null);

  const [detailOpen, setDetailOpen] = useState(defaultDetailOpen);
  const [preferredTab, setPreferredTab] = useState<'graph' | 'table' | 'raw' | null>(null);

  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);

  const nodeLabelKey = graphSettings?.node_label ?? 'label';
  const nodeColorByKey = graphSettings?.node_color_by ?? 'group';
  const edgeColor = theme.palette.divider;

  // Extract graph data from query results, supporting both explicit-graph and path formats.
  const graphData = useMemo(
    () => (records ? extractGraphData(records, nodeLabelKey) : null),
    [records, nodeLabelKey],
  );

  // Determine which tabs are available based on the current results.
  const availableTabs = useMemo<('graph' | 'table' | 'raw')[]>(() => {
    if (!records || records.length === 0) return [];
    const tabs: ('graph' | 'table' | 'raw')[] = [];
    if (graphData && graphData.nodes.length > 0) tabs.push('graph');
    tabs.push('table');
    tabs.push('raw');
    return tabs;
  }, [records, graphData]);

  // Active tab: user preference if still valid, otherwise first available.
  const activeTab = (preferredTab && availableTabs.includes(preferredTab))
    ? preferredTab
    : availableTabs[0] ?? 'table';

  useEffect(() => {
    if (needInputs === undefined || needInputs.length === 0) {
      runQuery(params);
    }
  }, [cypher, params, runQuery]);

  // Clear selection and tab preference when the query changes.
  useEffect(() => {
    setSelectedItem(null);
    setPreferredTab(null);
  }, [cypher]);

  // Rebuild XyFlow graph whenever extracted graph data changes.
  useEffect(() => {
    if (!graphData?.nodes?.length) {
      setNodes([]);
      setEdges([]);
      return;
    }
    const positions = computeLayout(graphData.nodes, graphData.links, 800, 450);
    setNodes(buildXyNodes(graphData.nodes, positions, nodeLabelKey, nodeColorByKey));
    setEdges(buildXyEdges(graphData.links, edgeColor));
  }, [graphData, nodeLabelKey, nodeColorByKey, edgeColor, setNodes, setEdges]);

  const handleNodeClick = (_: React.MouseEvent, node: Node) => {
    const original = node.data?.['original'] as GraphNode ?? node.data as unknown as GraphNode;
    setSelectedItem({ type: 'node', data: original });
    setDetailOpen(true);
  };

  const handleEdgeClick = (_: React.MouseEvent, edge: Edge) => {
    const original = edge.data?.['original'] as GraphLink ?? { source: edge.source, target: edge.target };
    setSelectedItem({ type: 'link', data: original as GraphLink });
    setDetailOpen(true);
  };

  const handlePaneClick = () => {
    setSelectedItem(null);
  };

  // ── Error / loading states ────────────────────────────────────────────────

  if (cypher === undefined) {
    return (
      <Card>
        <Grid container spacing={0} direction="column" alignItems="center">
          <CardHeader title={caption} />
        </Grid>
        <Divider />
        <Grid container spacing={0} direction="column" alignItems="center">
          <CardContent>
            <Error />
            <Typography variant="body2">Missing cypher query</Typography>
          </CardContent>
        </Grid>
      </Card>
    );
  }

  if (needInputs !== undefined && needInputs.length > 0) {
    return (
      <Card>
        <Grid container spacing={0} direction="column" alignItems="center">
          <CardHeader title={caption} />
        </Grid>
        <Divider />
        <Grid container spacing={0} direction="column" alignItems="center">
          <CardContent>
            <Typography variant="body2" align="center">
              (Set {needInputs.join(', ')})
            </Typography>
          </CardContent>
        </Grid>
      </Card>
    );
  }

  if (error) {
    return (
      <Typography variant="body2">
        Failed to load requested data, please reload.
      </Typography>
    );
  }

  if (queryErrors.length > 0) {
    return (
      <Card>
        <Grid container direction="column" alignItems="center">
          <CardHeader title={caption} />
        </Grid>
        <Divider />
        <QueryValidationBadge errors={queryErrors} warnings={warnings} />
        <Grid container spacing={0} direction="column" alignItems="center">
          <CardContent>
            <Typography variant="h4" align="center">N/A</Typography>
            <Typography variant="body2" align="center">Query validation failed</Typography>
          </CardContent>
        </Grid>
      </Card>
    );
  }

  if (loading || records === undefined) {
    return <ThreeDots color="#2BAD60" height="50" width="50" />;
  }

  if (records.length === 0) {
    return (
      <Card>
        <Grid container spacing={0} direction="column" alignItems="center">
          <CardHeader title={caption} />
        </Grid>
        <Divider />
        <CardContent>
          <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1, mb: 2 }}>
            <Error color="warning" fontSize="small" sx={{ mt: '2px', flexShrink: 0 }} />
            <Typography variant="body2">
              The query returned no results. If this is unexpected, check that the
              query returns graph data and that the MATCH clause finds data.
            </Typography>
          </Box>
          <Typography variant="caption" color="text.secondary" display="block" gutterBottom>
            Supported return formats
          </Typography>
          <Box
            sx={{
              bgcolor: 'action.hover',
              border: 1,
              borderColor: 'divider',
              borderRadius: 1,
              p: 1,
              fontFamily: 'monospace',
              fontSize: 12,
              whiteSpace: 'pre',
            }}
          >
            {[
              '// Option 1: explicit graph map',
              'RETURN {',
              '  nodes: [{ id, label, group, ...props }],',
              '  links: [{ source: <node id>, target: <node id>, type }]',
              '}',
              '',
              '// Option 2: RETURN path',
              'MATCH path = (a)-[*]->(b)',
              'RETURN path',
            ].join('\n')}
          </Box>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      {/* Header row: tabs left, caption right */}
      <Box sx={{ display: 'flex', alignItems: 'center', pl: 2 }}>
        <Tabs
          value={activeTab}
          onChange={(_, v: 'graph' | 'table' | 'raw') => setPreferredTab(v)}
          textColor="primary"
          indicatorColor="primary"
          sx={{ minHeight: 48, '& .MuiTab-root': { minHeight: 48 } }}
        >
          {availableTabs.includes('graph') && <Tab label="Graph" value="graph" />}
          {availableTabs.includes('table') && <Tab label="Table" value="table" />}
          {availableTabs.includes('raw') && <Tab label="Raw" value="raw" />}
        </Tabs>
        {caption && (
          <Typography variant="subtitle1" sx={{ ml: 'auto', pr: 2, color: 'text.secondary' }}>
            {caption}
          </Typography>
        )}
      </Box>
      <Divider />
      <QueryValidationBadge errors={queryErrors} warnings={warnings} />
      {/* ── Table tab ───────────────────────────────────────────────── */}
      {activeTab === 'table' && (
        <CypherTable cypher={cypher} params={params} needInputs={needInputs} height="400px" />
      )}

      {/* ── Raw tab ─────────────────────────────────────────────────── */}
      {activeTab === 'raw' && (
        <Box
          sx={{
            height: 450,
            overflow: 'auto',
            p: 2,
            fontFamily: 'monospace',
            fontSize: 12,
            bgcolor: 'action.hover',
            whiteSpace: 'pre',
          }}
        >
          {JSON.stringify(records, null, 2)}
        </Box>
      )}

      {/* ── Graph tab ───────────────────────────────────────────────── */}
      {activeTab === 'graph' && graphData && <Box sx={{ display: 'flex', height: 450 }}>
        {/* Graph canvas */}
        <Box
          sx={{
            flex: 1,
            height: 450,
            '--xy-controls-button-background-color': theme.palette.background.paper,
            '--xy-controls-button-background-color-hover': theme.palette.action.hover,
            '--xy-controls-button-color': theme.palette.text.primary,
            '--xy-controls-button-color-hover': theme.palette.text.primary,
            '--xy-controls-button-border-color': theme.palette.divider,
            '--xy-controls-box-shadow': theme.shadows[2],
            '& .react-flow__controls-button svg': {
              fill: theme.palette.text.primary,
            },
          }}
        >
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onNodeClick={handleNodeClick}
            onEdgeClick={handleEdgeClick}
            onPaneClick={handlePaneClick}
            nodeTypes={nodeTypes}
            fitView
            fitViewOptions={{ padding: 0.2 }}
            minZoom={0.1}
            maxZoom={4}
            style={{ background: theme.palette.background.paper }}
          >
            <Background
              variant={BackgroundVariant.Dots}
              color={theme.palette.divider}
              gap={20}
              size={1}
            />
            <Controls showInteractive={false} />
          </ReactFlow>
        </Box>

        {/* Toggle handle — always visible, attached to left edge of detail area */}
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'flex-start',
            pt: 1,
            borderLeft: 1,
            borderColor: 'divider',
            width: 28,
            flexShrink: 0,
          }}
        >
          <Tooltip title="Details" placement="left">
            <IconButton
              size="small"
              onClick={() => setDetailOpen(v => !v)}
              sx={{ color: detailOpen ? 'primary.main' : 'text.secondary' }}
            >
              {detailOpen ? <Info fontSize="small" /> : <InfoOutlined fontSize="small" />}
            </IconButton>
          </Tooltip>
        </Box>

        {/* Detail panel content — summary when nothing selected, item details when selected */}
        {detailOpen && (
          <Box
            sx={{
              width: DETAIL_PANEL_WIDTH,
              flexShrink: 0,
              borderLeft: 1,
              borderColor: 'divider',
              overflow: 'auto',
              p: 2,
            }}
          >
            {selectedItem ? (
              <GraphDetailPanel type={selectedItem.type} data={selectedItem.data} />
            ) : (
              <GraphSummaryPanel
                nodes={graphData.nodes}
                links={graphData.links}
                nodeGroupKey={nodeColorByKey}
                getColor={colorForGroup}
              />
            )}
          </Box>
        )}
      </Box>}
    </Card>
  );
}
