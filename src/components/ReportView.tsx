import { useState, useEffect, useCallback, useMemo, useRef, memo } from 'react';
import { Helmet } from 'react-helmet';
import {
  Box,
  Collapse,
  Container,
  Divider,
  IconButton,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography
} from '@mui/material';
import Error from '@mui/icons-material/Error';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import MuiMarkdown, { defaultOverrides } from 'mui-markdown';

import { Report, Panel, ReportInput } from 'src/config.context';
import { getQueryStringValue } from 'src/components/QueryString';
import CypherAutocomplete from 'src/components/reports/CypherAutocomplete';
import CypherBar from 'src/components/reports/CypherBar';
import CypherCount from 'src/components/reports/CypherCount';
import CypherGraph from 'src/components/reports/CypherGraph';
import CypherPie from 'src/components/reports/CypherPie';
import CypherProgress from 'src/components/reports/CypherProgress';
import CypherTable from 'src/components/reports/CypherTable';
import CypherVerticalTable from 'src/components/reports/CypherVerticalTable';
import FreeTextInput from 'src/components/reports/FreeTextInput';
import PanelGridRow from 'src/components/reports/PanelGridRow';
import {
  DASHBOARD_NAVBAR_HEIGHT,
  DASHBOARD_SIDEBAR_WIDTH_VAR
} from 'src/components/dashboardLayoutConstants';
import { contentContainerSx } from 'src/theme/layout';

const EMPTY_QUERY_CAPABILITIES: Record<string, string> = {};

function MarkdownTable({ children }: { children?: React.ReactNode }) {
  return (
    <TableContainer component={Paper} variant="outlined" sx={{ my: 2 }}>
      <Table size="small" sx={{ borderCollapse: 'collapse' }}>
        {children}
      </Table>
    </TableContainer>
  );
}

function MarkdownHeadCell({ children }: { children?: React.ReactNode }) {
  return (
    <TableCell
      component="th"
      scope="col"
      sx={{ whiteSpace: 'normal', border: '1px solid', borderColor: 'divider', fontWeight: 700, bgcolor: 'action.hover' }}
    >
      {children}
    </TableCell>
  );
}

function MarkdownCell({ children }: { children?: React.ReactNode }) {
  return (
    <TableCell sx={{ whiteSpace: 'normal', border: '1px solid', borderColor: 'divider' }}>
      {children}
    </TableCell>
  );
}

const markdownOverrides = {
  ...defaultOverrides,
  h1: { component: 'h2' as const },
  h2: { component: 'h3' as const },
  h3: { component: 'h4' as const },
  h4: { component: 'h5' as const },
  h5: { component: 'h6' as const },
  ol: { props: { className: 'mui-markdown-ol' } },
  ul: { props: { className: 'mui-markdown-ul' } },
  table: { component: MarkdownTable },
  thead: { component: TableHead },
  tbody: { component: TableBody },
  tr: { component: TableRow },
  th: { component: MarkdownHeadCell },
  td: { component: MarkdownCell },
};

interface PanelItemProps {
  item: Panel;
  rowIndex: number;
  index: number;
  varData: Record<string, { label?: string; value?: string }>;
  allInputs: ReportInput[];
  resolveQuery: (cypher: string | undefined) => string | undefined;
  resolveCapability: (path: string) => string | undefined;
}

const PanelItem = memo(function PanelItem({ item, rowIndex, index, varData, allInputs, resolveQuery, resolveCapability }: PanelItemProps) {
  const needInputs: string[] = [];
  const params: Record<string, string | undefined> = {};
  if (item.params !== undefined) {
    item.params.forEach((inputData) => {
      const paramName = inputData.name;
      const paramValue = inputData?.value;
      const paramInputId = inputData?.input_id;
      if (paramValue != null) {
        params[paramName] = paramValue;
      } else if (paramInputId != null) {
        params[paramName] = varData[paramInputId]?.value;
        if (
          params[paramName] === undefined ||
          params[paramName] === null ||
          params[paramName] === ''
        ) {
          try {
            const input = allInputs.find((obj) => obj.input_id === paramInputId);
            needInputs.push(input!.label);
          } catch (err) {
            console.log(err);
            needInputs.push(`*(Error: undefined input: ${paramInputId})`);
          }
        }
      }
    });
  }

  const effectiveCaption = item.hide_caption ? undefined : item.caption;

  const details = {
    cypher: resolveQuery(item.cypher),
    details_cypher: resolveQuery(item.details_cypher),
    type: item.type,
    columns: item.columns,
    caption: effectiveCaption,
    params,
    reportQueryToken: resolveCapability(`rows.${rowIndex}.panels.${index}.cypher`),
    detailsQueryToken: resolveCapability(`rows.${rowIndex}.panels.${index}.details_cypher`)
  };

  let itemComponent;
  if (item.type === 'progress') {
    itemComponent = (
        <CypherProgress
          cypher={resolveQuery(item.cypher)}
          params={params}
          caption={effectiveCaption}
          threshold={item.threshold}
          thresholds={item.thresholds}
          progressSettings={item.progress_settings}
          details={details}
          needInputs={needInputs}
          reportQueryToken={resolveCapability(`rows.${rowIndex}.panels.${index}.cypher`)}
        />
      );
  } else if (item.type === 'pie') {
    itemComponent = (
        <CypherPie
          cypher={resolveQuery(item.cypher)}
          params={params}
          caption={effectiveCaption}
          pieSettings={item.pie_settings}
          details={details}
          reportQueryToken={resolveCapability(`rows.${rowIndex}.panels.${index}.cypher`)}
        />
      );
  } else if (item.type === 'bar') {
    itemComponent = (
        <CypherBar
          cypher={resolveQuery(item.cypher)}
          params={params}
          caption={effectiveCaption}
          barSettings={item.bar_settings}
          details={details}
          reportQueryToken={resolveCapability(`rows.${rowIndex}.panels.${index}.cypher`)}
        />
      );
  } else if (item.type === 'graph') {
    itemComponent = (
        <CypherGraph
          cypher={resolveQuery(item.cypher)}
          params={params}
          caption={effectiveCaption}
          graphSettings={item.graph_settings}
          needInputs={needInputs}
          fillHeight
          reportQueryToken={resolveCapability(`rows.${rowIndex}.panels.${index}.cypher`)}
        />
      );
  } else if (item.type === 'count') {
    itemComponent = (
        <CypherCount
          cypher={resolveQuery(item.cypher)}
          params={params}
          caption={effectiveCaption}
          threshold={item.threshold}
          thresholds={item.thresholds}
          details={details}
          needInputs={needInputs}
          reportQueryToken={resolveCapability(`rows.${rowIndex}.panels.${index}.cypher`)}
        />
      );
  } else if (item.type === 'table') {
    itemComponent = (
        <CypherTable
          cypher={resolveQuery(item.cypher)}
          params={params}
          columns={item.columns}
          caption={effectiveCaption}
          details={details}
          needInputs={needInputs}
          reportQueryToken={resolveCapability(`rows.${rowIndex}.panels.${index}.cypher`)}
        />
      );
  } else if (item.type === 'vertical-table') {
    itemComponent = (
        <CypherVerticalTable
          cypher={resolveQuery(item.cypher)}
          params={params}
          id={item.table_id}
          details={details}
          needInputs={needInputs}
          autoHeight={item.auto_height ?? false}
          reportQueryToken={resolveCapability(`rows.${rowIndex}.panels.${index}.cypher`)}
        />
      );
  } else if (item.type === 'markdown') {
    itemComponent = (
      <Box sx={{
        ...(item.auto_height
          ? { height: 'auto' }
          : { height: '100%', minHeight: 0, overflow: 'auto' }),
        '& p': { mb: 1 },
        '& h2, & h3, & h4, & h5, & h6': { mb: 1 },
        '& ul, & ol': { mb: 1 },
        '& hr': { my: 2 },
        '& li:has(> input[type="checkbox"])': {
          listStyle: 'none',
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          ml: '-1.5em',
          '& p': { my: 0 },
        },
      }}>
        <MuiMarkdown options={{ overrides: markdownOverrides }}>
          {item.markdown}
        </MuiMarkdown>
      </Box>
    );
  }

  // ``auto_height`` panels render at content height; the parent grid grows
  // the cell to match. Other panels flex-fill their assigned cell.
  if (item.auto_height) {
    return <Box sx={{ width: '100%' }}>{itemComponent}</Box>;
  }
  return (
    <Box sx={{ height: '100%', minHeight: 0, display: 'flex', flexDirection: 'column' }}>
      {itemComponent}
    </Box>
  );
}, function areEqual(prevProps, nextProps) {
  if (prevProps.resolveQuery !== nextProps.resolveQuery) return false;
  if (prevProps.resolveCapability !== nextProps.resolveCapability) return false;
  if (prevProps.rowIndex !== nextProps.rowIndex) return false;
  if (prevProps.index !== nextProps.index) return false;
  if (prevProps.item !== nextProps.item) return false;

  // Only re-render if a varData value for an input this panel uses has changed
  const inputIds = (nextProps.item.params ?? [])
    .map((p) => p.input_id)
    .filter((id): id is string => id != null);

  for (const id of inputIds) {
    if (prevProps.varData[id]?.value !== nextProps.varData[id]?.value) return false;
  }
  return true;
});

interface ReportViewProps {
  report: Report;
  title?: string;
  showTitle?: boolean;
  boxSx?: object;
  queryCapabilities?: Record<string, string>;
  toolbarActions?: React.ReactNode;
  stickyToolbar?: boolean;
}

function inputWidth(size?: number) {
  if (size === undefined) return 220;
  return Math.min(Math.max(size * 70, 180), 420);
}

function ReportView({
  report,
  title,
  showTitle = false,
  boxSx = { minHeight: '100%', pb: 3 },
  queryCapabilities,
  toolbarActions,
  stickyToolbar = true
}: ReportViewProps) {
  const displayTitle = title ?? report.name;
  const reportQueries = useMemo(() => report.queries ?? {}, [report]);
  const capabilities = queryCapabilities ?? EMPTY_QUERY_CAPABILITIES;
  const resolveQuery = useCallback((cypher: string | undefined): string | undefined => {
    if (cypher === undefined) return undefined;
    return reportQueries[cypher] ?? cypher;
  }, [reportQueries]);
  const resolveCapability = useCallback((path: string): string | undefined => capabilities[path], [capabilities]);
  const [varData, setVarData] = useState({});
  const toolbarRef = useRef<HTMLDivElement | null>(null);
  const [toolbarHeight, setToolbarHeight] = useState(64);
  const [collapsedRows, setCollapsedRows] = useState<Record<number, boolean>>({});

  useEffect(() => {
    const initialVarState = {};
    if (report.inputs) {
      report.inputs.forEach((input) => {
        const inputValue = getQueryStringValue(input.input_id);
        if (inputValue !== undefined) {
          // TODO(ryan-lane): Figure out a way to pass the label along with the value in the param
          initialVarState[input.input_id] = { label: inputValue, value: inputValue };
        } else if (input.default !== undefined) {
          initialVarState[input.input_id] = input.default;
        } else {
          initialVarState[input.input_id] = {};
        }
      });
    }
    setVarData(initialVarState);
  }, [report]);

  const inputControls: React.ReactNode[] = [];
  if (report.inputs) {
    report.inputs.forEach((input, index) => {
      if (input === undefined) {
        inputControls.push(
          <Box
            key={`undefined-input-${index}`}
            sx={{
              minWidth: 180,
              width: { xs: '100%', sm: inputWidth() }
            }}
          >
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Error />
              <Typography>Undefined input</Typography>
            </Box>
          </Box>
        );
        return;
      }

      let inputComponent;
      if (input.type === 'autocomplete') {
        inputComponent = (
          <CypherAutocomplete
            cypher={input.cypher}
            params={input.params}
            inputId={input.input_id}
            inputDefault={input.default}
            labelName={input.label}
            value={varData}
            setValue={setVarData}
            reportQueryToken={resolveCapability(`inputs.${index}.cypher`)}
            size="small"
          />
        );
      } else if (input.type === 'text') {
        inputComponent = (
          <FreeTextInput
            inputId={input.input_id}
            inputDefault={input.default}
            labelName={input.label}
            value={varData}
            setValue={setVarData}
            size="small"
          />
        );
      }

      inputControls.push(
        <Box
          key={input.input_id}
          sx={{
            flex: { xs: '1 1 100%', sm: `0 1 ${inputWidth(input.size)}px` },
            minWidth: { xs: '100%', sm: 180 },
            maxWidth: { xs: 'none', sm: inputWidth(input.size) }
          }}
        >
          {inputComponent}
        </Box>
      );
    });
  }

  useEffect(() => {
    if (!stickyToolbar || toolbarRef.current === null) return undefined;

    const updateToolbarHeight = () => {
      setToolbarHeight(toolbarRef.current?.offsetHeight ?? 64);
    };

    updateToolbarHeight();
    if (typeof ResizeObserver === 'undefined') return undefined;

    const observer = new ResizeObserver(updateToolbarHeight);
    observer.observe(toolbarRef.current);
    return () => observer.disconnect();
  }, [stickyToolbar, inputControls.length, toolbarActions]);

  const hasToolbar = inputControls.length > 0 || toolbarActions !== undefined;
  const toolbar = hasToolbar ? (
    <Box
      ref={toolbarRef}
      sx={{
        position: stickyToolbar ? 'fixed' : 'static',
        top: stickyToolbar ? DASHBOARD_NAVBAR_HEIGHT : 'auto',
        right: stickyToolbar ? 0 : 'auto',
        left: stickyToolbar ? { xs: 0, lg: `var(${DASHBOARD_SIDEBAR_WIDTH_VAR})` } : 'auto',
        zIndex: (theme) => theme.zIndex.appBar - 1,
        bgcolor: 'background.paper',
        borderBottom: 1,
        borderColor: 'divider',
        boxShadow: stickyToolbar ? 1 : 'none',
        ...contentContainerSx,
        py: 2,
        mb: stickyToolbar ? 0 : 2,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 1.5,
        flexWrap: 'wrap'
      }}
    >
      {inputControls.length > 0 && (
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 1,
            flex: '1 1 320px',
            flexWrap: 'wrap',
            minWidth: 0
          }}
        >
          {inputControls}
        </Box>
      )}
      {toolbarActions && (
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'flex-end',
            gap: 1,
            flex: inputControls.length > 0 ? '0 0 auto' : '1 1 auto',
            flexWrap: 'wrap',
            ml: 'auto',
            '& .MuiButton-root': {
              minHeight: 40
            },
            '& .MuiIconButton-root': {
              height: 40,
              width: 40
            },
            '& .MuiChip-root': {
              height: 32
            }
          }}
        >
          {toolbarActions}
        </Box>
      )}
    </Box>
  ) : null;

  const toggleRowCollapsed = useCallback((rowIndex: number) => {
    setCollapsedRows((prev) => ({ ...prev, [rowIndex]: !prev[rowIndex] }));
  }, []);

  const rows = report.rows.map((row, rowIndex) => {
    // collapsible defaults to true; only disabled when explicitly set false
    const effectiveCollapsible = row.collapsible !== false;
    const isCollapsed = effectiveCollapsible && collapsedRows[rowIndex] === true;
    const hideHeader = row.hide_header === true;

    const collapseBtn = effectiveCollapsible ? (
      <IconButton
        className="row-collapse-btn"
        size="small"
        onClick={() => toggleRowCollapsed(rowIndex)}
        aria-label={isCollapsed ? `Expand ${row.name}` : `Collapse ${row.name}`}
        aria-expanded={!isCollapsed}
        sx={{
          opacity: isCollapsed ? 1 : 0,
          transition: 'opacity 0.15s',
          '&:focus-visible': { opacity: 1 },
          flexShrink: 0,
        }}
      >
        <ExpandMoreIcon
          sx={{
            transition: 'transform 0.2s',
            transform: isCollapsed ? 'rotate(-90deg)' : 'none',
          }}
        />
      </IconButton>
    ) : null;

    const panelArea = (
      <Box sx={{ py: 1.5 }}>
        <PanelGridRow
          panels={row.panels}
          renderPanel={(item, index) => (
            <PanelItem
              rowIndex={rowIndex}
              index={index}
              item={item}
              varData={varData}
              allInputs={report.inputs ?? []}
              resolveQuery={resolveQuery}
              resolveCapability={resolveCapability}
            />
          )}
        />
      </Box>
    );

    return (
      <Container key={row.name} maxWidth={false} sx={{ ...contentContainerSx, pb: 1.5 }}>
        <Paper
          elevation={1}
          sx={{
            p: 1.5,
            // Remove top padding when header is hidden so the row is visually compact
            pt: hideHeader ? 0 : 1.5,
            ...(effectiveCollapsible && {
              '&:hover .row-collapse-btn': { opacity: 1 },
            }),
          }}
        >
          {hideHeader ? (
            // No title — show a minimal right-aligned toggle so the row can still be collapsed
            effectiveCollapsible && (
              <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
                {collapseBtn}
              </Box>
            )
          ) : (
            <>
              <Box sx={{ display: 'flex', alignItems: 'center' }}>
                <Typography variant="h2" sx={{ mb: 0, flex: 1 }}>
                  {row.name}
                </Typography>
                {collapseBtn}
              </Box>
              <Divider sx={{ mt: 1, mb: 0 }} />
            </>
          )}
          {effectiveCollapsible ? (
            <Collapse in={!isCollapsed} timeout="auto">
              {panelArea}
            </Collapse>
          ) : panelArea}
        </Paper>
      </Container>
    );
  });

  return (
    <>
      {displayTitle && (
        <Helmet>
          <title>{displayTitle} | Seizu</title>
        </Helmet>
      )}
      <Box sx={boxSx}>
        {toolbar}
        {hasToolbar && stickyToolbar && <Box sx={{ height: toolbarHeight }} />}
        {showTitle && displayTitle && (
          <Box
            sx={{
              bgcolor: 'background.paper',
              borderBottom: 1,
              borderColor: 'divider',
              mb: 2
            }}
          >
            <Container
              maxWidth={false}
              sx={{
                ...contentContainerSx,
                py: 1.75
              }}
            >
              <Typography component="h1" variant="h2" sx={{ lineHeight: 1.25 }}>
                {displayTitle}
              </Typography>
            </Container>
          </Box>
        )}
        <Box>
          {rows}
        </Box>
      </Box>
    </>
  );
}

export default ReportView;
