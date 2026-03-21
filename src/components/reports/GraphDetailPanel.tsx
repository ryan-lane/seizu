import { Box, Divider, Typography } from '@mui/material';
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

export default function GraphDetailPanel({ type, data }: GraphDetailPanelProps) {
  // `data` is the original backend object. For links, source/target are IDs (strings/numbers)
  // since we store the raw backend GraphLink, not the XyFlow-processed edge.
  const entries = Object.entries(data).filter(([k]) => !GRAPH_INTERNAL_PROPS.has(k));

  return (
    <Box>
      <Typography variant="overline" color="text.secondary" display="block" gutterBottom>
        {type === 'node' ? 'Node' : 'Relationship'}
      </Typography>
      {entries.map(([k, v]) => (
        <Box key={k} sx={{ mb: 1.5 }}>
          <Typography variant="caption" color="text.secondary" display="block">
            {k}
          </Typography>
          <Typography variant="body2" sx={{ wordBreak: 'break-all' }}>
            {typeof v === 'object' && v !== null ? JSON.stringify(v) : String(v ?? '')}
          </Typography>
          <Divider sx={{ mt: 1 }} />
        </Box>
      ))}
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
    const g = String(n[nodeGroupKey] ?? 'default');
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
