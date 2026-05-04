import { useCallback, useEffect, useRef, useState } from 'react';
import Error from '@mui/icons-material/Error';
import {
  Box,
  Button,
  Dialog,
  DialogContent,
  DialogActions,
  IconButton,
  Paper,
  Skeleton,
  Tooltip,
  Typography
} from '@mui/material';
import MUIDataTable from 'mui-datatables';
import Info from '@mui/icons-material/Info';
import Fullscreen from '@mui/icons-material/Fullscreen';
import CloseFullscreen from '@mui/icons-material/CloseFullscreen';

import { useLazyCypherQuery, QueryRecord } from 'src/hooks/useCypherQuery';

/**
 * Format any value for display in a table cell.
 *
 * Understands the Neo4j serialization shapes produced by the backend:
 *  - Node:         {id, labels, properties}  → "(Label) name"
 *  - Relationship: {id, type, start_node_id} → "[TYPE]"
 *  - Path:         {nodes, relationships}    → node labels joined with " → "
 *  - Array:        each element formatted recursively, joined with ", "
 *  - Plain object: "key: value" pairs joined with ", "
 *  - Primitive:    String(value)
 */
function formatValue(val: unknown): string {
  if (val === null || val === undefined) return '';
  if (typeof val !== 'object') return String(val);
  if (Array.isArray(val)) return val.map(formatValue).join(', ');

  const obj = val as Record<string, unknown>;

  // Neo4j node: {id, labels: [...], properties: {...}}
  if (Array.isArray(obj.labels) && typeof obj.properties === 'object' && obj.properties !== null) {
    const label = (obj.labels as string[])[0] ?? '';
    const props = obj.properties as Record<string, unknown>;
    const name = props['name'] ?? props['id'] ?? obj['id'];
    return label ? `(${label}) ${String(name)}` : String(name);
  }

  // Neo4j relationship: {type, start_node_id, end_node_id, ...}
  if (typeof obj['type'] === 'string' && 'start_node_id' in obj) {
    return `[${obj['type']}]`;
  }

  // Path: {nodes: [...], relationships: [...]}
  if (Array.isArray(obj['nodes']) && Array.isArray(obj['relationships'])) {
    return (obj['nodes'] as unknown[]).map(formatValue).join(' → ');
  }

  // Generic object: "key: value" pairs
  return Object.entries(obj)
    .filter(([, v]) => v !== null && v !== undefined)
    .map(([k, v]) => `${k}: ${formatValue(v)}`)
    .join(', ');
}

/**
 * Flatten a query record into a plain key→value map suitable for table display.
 *
 * Handles three shapes:
 *  - Multiple columns: `RETURN n.name AS name, n.org AS org`  → use record as-is
 *  - Single key, plain object: `RETURN {name: n.name} AS row` → unwrap the value
 *  - Single key, Neo4j node: `RETURN n` or `RETURN n AS x`   → unwrap `.properties`
 */
function flattenRecord(record: QueryRecord): QueryRecord {
  const keys = Object.keys(record);
  if (keys.length === 1) {
    const val = record[keys[0]];
    if (val && typeof val === 'object' && !Array.isArray(val)) {
      const obj = val as QueryRecord;
      if (obj.properties && typeof obj.properties === 'object' && !Array.isArray(obj.properties)) {
        return obj.properties as QueryRecord;
      }
      return obj;
    }
  }
  return record;
}
import CypherDetails from 'src/components/reports/CypherDetails';
import QueryValidationBadge from 'src/components/reports/QueryValidationBadge';

function TableLoadingSkeleton({ height }: { height?: string }) {
  const bodyHeight = height ?? '475px';

  return (
    <Paper data-testid="cypher-table-loading-skeleton" variant="outlined" sx={{ overflow: 'hidden' }}>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', minHeight: 44, px: 1 }}>
        <Skeleton variant="text" width={180} height={22} />
        <Box sx={{ display: 'flex', gap: 0.5 }}>
          <Skeleton variant="circular" width={24} height={24} />
          <Skeleton variant="circular" width={24} height={24} />
          <Skeleton variant="circular" width={24} height={24} />
          <Skeleton variant="circular" width={24} height={24} />
        </Box>
      </Box>
      <Box sx={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr 1fr', alignItems: 'center', minHeight: 40, gap: 2, px: 1.5, borderTop: 1, borderBottom: 1, borderColor: 'divider' }}>
        <Skeleton variant="text" height={20} />
        <Skeleton variant="text" height={20} />
        <Skeleton variant="text" height={20} />
      </Box>
      <Box sx={{ height: bodyHeight, px: 1.5, py: 1 }}>
        {Array.from({ length: 8 }).map((_, index) => (
          // eslint-disable-next-line react/no-array-index-key
          <Box key={index} sx={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr 1fr', gap: 2, py: 0.75 }}>
            <Skeleton variant="text" height={20} />
            <Skeleton variant="text" height={20} />
            <Skeleton variant="text" height={20} />
          </Box>
        ))}
      </Box>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', minHeight: 40, gap: 2, px: 1.5, borderTop: 1, borderColor: 'divider' }}>
        <Skeleton variant="text" width={90} height={20} />
        <Skeleton variant="text" width={120} height={20} />
      </Box>
    </Paper>
  );
}

// Approximate height consumed by the (compact) mui-datatables chrome:
// toolbar ~44, column header ~40, pagination footer ~40. The optional
// caption above the table is added on top of this when present.
const TABLE_CHROME_HEIGHT = 124;
const CAPTION_HEIGHT = 28;
const MIN_TABLE_BODY_HEIGHT = 120;

// Override MUI Toolbar / Table / Pagination defaults to a tighter density so
// the table body has more vertical room inside the panel cell.
const fillSx = {
  height: '100%',
  display: 'flex',
  flexDirection: 'column' as const,
  minHeight: 0,
  '& .MuiToolbar-root': {
    minHeight: 44,
    paddingLeft: 1,
    paddingRight: 1
  },
  '& .MuiTableCell-head': {
    paddingTop: 0.5,
    paddingBottom: 0.5,
    lineHeight: 1.2
  },
  '& .MuiTablePagination-root': {
    minHeight: 40
  },
  '& .MuiTablePagination-toolbar': {
    minHeight: 40,
    paddingLeft: 1,
    paddingRight: 1
  },
  '& .MuiIconButton-root': {
    padding: 0.5
  }
};

interface CypherTableProps {
  cypher?: string;
  params?: Record<string, unknown>;
  columns?: Array<{ name: string; label: string }>;
  caption?: string;
  needInputs?: string[];
  details?: Record<string, unknown>;
  height?: string;
  reportQueryToken?: string;
}

export default function CypherTable({
  cypher,
  params,
  columns,
  caption,
  needInputs,
  details,
  height,
  reportQueryToken
}: CypherTableProps) {
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [expandOpen, setExpandOpen] = useState(false);
  const [expandSize, setExpandSize] = useState(window.innerHeight);
  const [containerHeight, setContainerHeight] = useState<number | null>(null);
  const observerRef = useRef<ResizeObserver | null>(null);
  const [runQuery, { loading, error, records, first, warnings, queryErrors }] =
    useLazyCypherQuery(cypher, reportQueryToken);

  // Callback ref so the ResizeObserver re-attaches whenever the container DOM
  // node swaps — the component renders different outer Boxes for the loading,
  // empty, and loaded states.
  const containerRef = useCallback((node: HTMLDivElement | null) => {
    if (typeof ResizeObserver === 'undefined') return;
    if (observerRef.current) {
      observerRef.current.disconnect();
      observerRef.current = null;
    }
    if (!node) return;
    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) return;
      setContainerHeight(entry.contentRect.height);
    });
    observer.observe(node);
    observerRef.current = observer;
  }, []);

  useEffect(() => {
    function handleResize() {
      setExpandSize(window.innerHeight);
    }

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  useEffect(() => {
    return () => {
      observerRef.current?.disconnect();
      observerRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (needInputs === undefined || needInputs.length === 0) {
      runQuery(params);
    }
  }, [cypher, params, runQuery]);

  if (error) {
    console.log(error);
    return (
      <Box ref={containerRef} sx={fillSx}>
        <Typography variant="body2">
          Failed to load requested data, please reload.
        </Typography>
      </Box>
    );
  }

  if (cypher === undefined) {
    return (
      <Box ref={containerRef} sx={fillSx}>
        <Error />
        <Typography variant="body2">Missing cypher query</Typography>
      </Box>
    );
  }

  if (queryErrors.length > 0) {
    return (
      <Box ref={containerRef} sx={fillSx}>
        <Typography variant="subtitle1" component="div" sx={{ fontWeight: 500, mb: 0.5 }}>
          {caption}
          <QueryValidationBadge errors={queryErrors} warnings={warnings} />
        </Typography>
        <Typography variant="body2">Query validation failed.</Typography>
      </Box>
    );
  }

  const setOpenDetails = () => {
    setDetailsOpen(true);
  };

  const setOpenExpand = () => {
    setExpandOpen(true);
  };

  const setClosedExpand = () => {
    setExpandOpen(false);
  };

  let tableBodyHeight = '';
  let tableBodySkeletonHeight = '';

  const options: Record<string, unknown> & { responsive: string; selectableRows: string; print: boolean } = {
    responsive: 'simple',
    selectableRows: 'none',
    print: false,
    customToolbar: () => {
      const icons = [];
      if (warnings.length > 0 || queryErrors.length > 0) {
        icons.push(
          <QueryValidationBadge key="validation" errors={queryErrors} warnings={warnings} />
        );
      }
      if (details !== undefined) {
        icons.push(
          <Tooltip key="info" title="Show query details">
            <IconButton size="small" onClick={setOpenDetails}>
              <Info fontSize="small" />
            </IconButton>
          </Tooltip>
        );
      }
      if (expandOpen === false) {
        icons.push(
          <Tooltip key="fullscreen" title="Fullscreen">
            <IconButton size="small" onClick={setOpenExpand}>
              <Fullscreen fontSize="small" />
            </IconButton>
          </Tooltip>
        );
      } else {
        icons.push(
          <Tooltip key="fullscreen" title="Close Fullscreen">
            <IconButton size="small" onClick={setClosedExpand}>
              <CloseFullscreen fontSize="small" />
            </IconButton>
          </Tooltip>
        );
      }
      return icons;
    }
  };

  if (expandOpen) {
    // window height minus the size of the table header and footer
    tableBodyHeight = `${expandSize - 225}px`;
    tableBodySkeletonHeight = tableBodyHeight;
    options.tableBodyHeight = tableBodyHeight;
    options.rowsPerPage = '100';
  } else if (height !== undefined) {
    tableBodyHeight = height;
    tableBodySkeletonHeight = height;
    options.tableBodyHeight = height;
  } else if (containerHeight !== null) {
    // Fill the parent cell, leaving room for the mui-datatables chrome and
    // (when present) the caption rendered above the table.
    const chrome = TABLE_CHROME_HEIGHT + (caption ? CAPTION_HEIGHT : 0);
    const bodyPx = Math.max(containerHeight - chrome, MIN_TABLE_BODY_HEIGHT);
    tableBodyHeight = `${bodyPx}px`;
    tableBodySkeletonHeight = tableBodyHeight;
    options.tableBodyHeight = tableBodyHeight;
  } else {
    // First render before ResizeObserver fires — use a sensible default.
    tableBodyHeight = `${MIN_TABLE_BODY_HEIGHT}px`;
    tableBodySkeletonHeight = tableBodyHeight;
    options.tableBodyHeight = tableBodyHeight;
  }

  if (needInputs !== undefined && needInputs.length > 0) {
    const noMatchMessage = `Select ${needInputs.join(', ')} to load results`;
    const needInputsOptions = {
      ...options,
      textLabels: { body: { noMatch: noMatchMessage } }
    };
    return (
      <Box ref={containerRef} sx={fillSx}>
        {caption && (
          <Typography variant="subtitle1" sx={{ fontWeight: 500, mb: 0.5 }}>
            {caption}
          </Typography>
        )}
        <MUIDataTable
          data={[]}
          columns={columns ?? []}
          options={needInputsOptions}
        />
      </Box>
    );
  }

  if (loading || records === undefined) {
    return (
      <Box ref={containerRef} sx={fillSx}>
        {caption && (
          <Typography variant="subtitle1" sx={{ fontWeight: 500, mb: 0.5 }}>
            {caption}
          </Typography>
        )}
        <TableLoadingSkeleton height={tableBodySkeletonHeight} />
      </Box>
    );
  }

  if (records === null || records.length === 0) {
    return (
      <Box ref={containerRef} sx={fillSx}>
        <Typography variant="body2">No records found.</Typography>
      </Box>
    );
  }

  if (first === undefined) {
    return (
      <Box ref={containerRef} sx={fillSx}>
        <MUIDataTable data={[]} columns={[]} options={options} />
      </Box>
    );
  }

  const mungedColumns = [];
  if (columns === undefined) {
    Object.keys(flattenRecord(first)).forEach((column) => {
      mungedColumns.push({ name: column, label: column });
    });
  } else {
    columns.forEach((column) => mungedColumns.push(column));
  }

  const mungedRecords = [];
  for (let i = 0; i < records.length; i++) {
    const mungedData = columns === undefined ? flattenRecord(records[i]) : { ...records[i] };
    Object.keys(mungedData).forEach((key) => {
      const val = mungedData[key];
      if (typeof val === 'object' && val !== null) {
        mungedData[key] = formatValue(val);
      }
    });
    mungedRecords.push(mungedData);
  }

  return (
    <Box ref={containerRef} sx={fillSx}>
      <Typography gutterBottom variant="h4">
        {caption}
      </Typography>
      <MUIDataTable
        data={mungedRecords}
        columns={mungedColumns}
        options={options}
      />
      {details !== undefined && (
        <CypherDetails
          details={details}
          open={detailsOpen}
          setOpen={setDetailsOpen}
        />
      )}
      <Dialog fullScreen open={expandOpen} onClose={setClosedExpand}>
        <DialogContent>
          <MUIDataTable
            data={mungedRecords}
            columns={mungedColumns}
            options={options}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={setClosedExpand} color="primary" autoFocus>
            Close
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
