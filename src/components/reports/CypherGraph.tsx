import { useEffect, useRef, useCallback } from 'react';
import {
  Box,
  Card,
  CardContent,
  CardHeader,
  Divider,
  Grid,
  Typography
} from '@mui/material';
import { useTheme, alpha } from '@mui/material/styles';
import Error from '@mui/icons-material/Error';
import { ThreeDots } from 'react-loader-spinner';
import ForceGraph2D from 'react-force-graph-2d';
import { useLazyCypherQuery } from 'src/hooks/useCypherQuery';
import QueryValidationBadge from 'src/components/reports/QueryValidationBadge';

interface GraphSettings {
  node_label?: string;
  node_color_by?: string;
}

interface GraphNode {
  id: string | number;
  label?: string;
  group?: string;
  [key: string]: unknown;
}

interface GraphLink {
  source: string | number;
  target: string | number;
  type?: string;
  [key: string]: unknown;
}

interface GraphData {
  nodes: GraphNode[];
  links: GraphLink[];
}

interface CypherGraphProps {
  cypher?: string;
  params?: Record<string, unknown>;
  caption?: string;
  graphSettings?: GraphSettings;
  needInputs?: string[];
}

// MUI-compatible categorical palette — same colours used by @mui/x-charts default theme
const PALETTE = [
  '#02B2AF', '#2E96FF', '#B800D8', '#60009B',
  '#2731C8', '#03008D', '#00B929', '#FF5733',
  '#FFA500', '#E91E63'
];

function colorForGroup(group: string, colorMap: Map<string, string>): string {
  if (!colorMap.has(group)) {
    colorMap.set(group, PALETTE[colorMap.size % PALETTE.length]);
  }
  return colorMap.get(group)!;
}

const NODE_R = 6;

export default function CypherGraph({
  cypher,
  params,
  caption,
  graphSettings,
  needInputs
}: CypherGraphProps) {
  const theme = useTheme();
  const containerRef = useRef<HTMLDivElement>(null);

  const [runQuery, { loading, error, records, first, warnings, queryErrors }] =
    useLazyCypherQuery(cypher);

  useEffect(() => {
    if (needInputs === undefined || needInputs.length === 0) {
      runQuery(params);
    }
  }, [cypher, params, runQuery]);

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

  if (first === undefined) {
    return (
      <Card>
        <Grid container spacing={0} direction="column" alignItems="center">
          <CardHeader title={caption} />
        </Grid>
        <Divider />
        <Grid container spacing={0} direction="column" alignItems="center">
          <CardContent>
            <Typography variant="h4">N/A</Typography>
          </CardContent>
        </Grid>
      </Card>
    );
  }

  const rawGraph = first['graph'] as GraphData | undefined;
  if (!rawGraph || !Array.isArray(rawGraph.nodes)) {
    return (
      <Card>
        <Grid container spacing={0} direction="column" alignItems="center">
          <CardHeader title={caption} />
        </Grid>
        <Divider />
        <Grid container spacing={0} direction="column" alignItems="center">
          <CardContent>
            <Error />
            <Typography variant="body2">
              Query must return a single record with a <code>graph</code> key containing{' '}
              <code>{'{ nodes: [...], links: [...] }'}</code>.
            </Typography>
          </CardContent>
        </Grid>
      </Card>
    );
  }

  const nodeLabelKey = graphSettings?.node_label ?? 'label';
  const nodeColorByKey = graphSettings?.node_color_by ?? 'group';
  const colorMap = new Map<string, string>();

  const isDark = theme.palette.mode === 'dark';
  const bgColor = theme.palette.background.paper;
  const textColor = theme.palette.text.primary;
  const textSecondary = theme.palette.text.secondary;
  // Use the theme divider colour for links
  const linkCol = theme.palette.divider;
  // Arrow colour slightly more prominent
  const arrowCol = isDark
    ? alpha(theme.palette.text.secondary, 0.6)
    : alpha(theme.palette.text.secondary, 0.5);

  // Draw each node as a themed circle + label
  const paintNode = useCallback(
    (node: object, ctx: CanvasRenderingContext2D, globalScale: number) => {
      const n = node as GraphNode;
      const x = n.x as number ?? 0;
      const y = n.y as number ?? 0;
      const groupVal = String(n[nodeColorByKey] ?? 'default');
      const nodeColor = colorForGroup(groupVal, colorMap);
      const label = String(n[nodeLabelKey] ?? n.id ?? '');

      // Node circle
      ctx.beginPath();
      ctx.arc(x, y, NODE_R, 0, 2 * Math.PI);
      ctx.fillStyle = nodeColor;
      ctx.fill();
      // Subtle ring matching the paper bg so nodes pop on the background
      ctx.strokeStyle = bgColor;
      ctx.lineWidth = 1.5;
      ctx.stroke();

      // Label below the node — only render when zoomed in enough to be readable
      const fontSize = Math.max(6, 11 / globalScale);
      if (globalScale >= 0.6) {
        ctx.font = `${fontSize}px ${theme.typography.fontFamily ?? 'sans-serif'}`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';
        // Pill background so label is legible on any background
        const textWidth = ctx.measureText(label).width;
        const padding = 2 / globalScale;
        const bx = x - textWidth / 2 - padding;
        const by = y + NODE_R + 2 / globalScale;
        const bw = textWidth + padding * 2;
        const bh = fontSize + padding * 2;
        ctx.fillStyle = alpha(bgColor, 0.75);
        ctx.fillRect(bx, by, bw, bh);
        ctx.fillStyle = textSecondary;
        ctx.fillText(label, x, by + padding);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [nodeLabelKey, nodeColorByKey, bgColor, textSecondary, theme.typography.fontFamily]
  );

  return (
    <Card>
      <Grid container direction="column" alignItems="center">
        <CardHeader title={caption} />
      </Grid>
      <Divider />
      <QueryValidationBadge errors={queryErrors} warnings={warnings} />
      {/* Tooltip styling injected via a Box wrapper so the canvas-based
          tooltip div picks up theme colours without a global stylesheet. */}
      <Box
        ref={containerRef}
        sx={{
          height: 450,
          width: '100%',
          overflow: 'hidden',
          // ForceGraph2D renders an absolutely positioned tooltip div;
          // target it by its fixed class name.
          '& #graph-tooltip': {
            background: theme.palette.background.paper,
            border: `1px solid ${theme.palette.divider}`,
            borderRadius: `${theme.shape.borderRadius}px`,
            color: theme.palette.text.primary,
            fontFamily: theme.typography.fontFamily,
            fontSize: theme.typography.caption.fontSize,
            padding: '4px 8px',
            boxShadow: theme.shadows[2],
            pointerEvents: 'none'
          }
        }}
      >
        <ForceGraph2D
          graphData={rawGraph}
          backgroundColor={bgColor}
          linkColor={() => linkCol}
          linkWidth={1.5}
          linkDirectionalArrowLength={5}
          linkDirectionalArrowRelPos={1}
          linkDirectionalArrowColor={() => arrowCol}
          nodeLabel={(node) => String((node as GraphNode)[nodeLabelKey] ?? (node as GraphNode).id ?? '')}
          nodeRelSize={NODE_R}
          nodeCanvasObject={paintNode}
          nodeCanvasObjectMode={() => 'replace'}
          width={containerRef.current?.clientWidth ?? 800}
          height={450}
        />
      </Box>
    </Card>
  );
}
