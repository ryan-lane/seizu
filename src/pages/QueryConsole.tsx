import { useCallback, useEffect, useRef, useState } from 'react';
import {
  Box,
  Button,
  Card,
  CardContent,
  CircularProgress,
  TextField,
  Typography
} from '@mui/material';
import PlayArrow from '@mui/icons-material/PlayArrow';
import CypherGraph from 'src/components/reports/CypherGraph';
import QueryConsoleSchemaPanel from 'src/components/QueryConsoleSchemaPanel';
import { usePermissionState } from 'src/hooks/usePermissions';
import { pageContentSx } from 'src/theme/layout';

const QUERY_CONSOLE_SCHEMA_PANEL_STORAGE_KEY = 'seizu:query-console:schema-panel-open';

export default function QueryConsole() {
  const { hasPermission, loading: permissionsLoading } = usePermissionState();
  const [queryText, setQueryText] = useState('');
  const [submittedQuery, setSubmittedQuery] = useState<string | undefined>(
    undefined
  );
  const [schemaPanelOpen, setSchemaPanelOpen] = useState(() => {
    if (typeof window === 'undefined') return true;
    const storedValue = window.localStorage.getItem(QUERY_CONSOLE_SCHEMA_PANEL_STORAGE_KEY);
    return storedValue === null ? true : storedValue === 'true';
  });
  const [historyRefreshTrigger, setHistoryRefreshTrigger] = useState(0);
  const [queryHeight, setQueryHeight] = useState(220);
  const dragStartY = useRef(0);
  const dragStartHeight = useRef(0);

  const handleQueryComplete = useCallback(() => {
    setHistoryRefreshTrigger((n) => n + 1);
  }, []);

  const handleRun = () => {
    const trimmed = queryText.trim();
    if (!trimmed) return;
    setSubmittedQuery(trimmed);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      handleRun();
    }
  };

  /** Insert a query from the schema browser and run it immediately. */
  const handleQuerySelect = (query: string) => {
    setQueryText(query);
    setSubmittedQuery(query);
  };

  /** Load a query from history into the editor without running it. */
  const handleHistorySelect = (query: string) => {
    setQueryText(query);
  };

  const handleSchemaPanelToggle = (tab?: 'schema' | 'history') => {
    if (tab) {
      setSchemaPanelOpen(true);
      return;
    }
    setSchemaPanelOpen((value) => !value);
  };

  useEffect(() => {
    window.localStorage.setItem(
      QUERY_CONSOLE_SCHEMA_PANEL_STORAGE_KEY,
      String(schemaPanelOpen)
    );
  }, [schemaPanelOpen]);

  const handleDragStart = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      dragStartY.current = e.clientY;
      dragStartHeight.current = queryHeight;
      document.body.style.cursor = 'ns-resize';
      document.body.style.userSelect = 'none';

      const handleMouseMove = (ev: MouseEvent) => {
        const delta = dragStartY.current - ev.clientY;
        setQueryHeight(
          Math.max(100, Math.min(600, dragStartHeight.current + delta))
        );
      };

      const handleMouseUp = () => {
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
        document.removeEventListener('mousemove', handleMouseMove);
        document.removeEventListener('mouseup', handleMouseUp);
      };

      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
    },
    [queryHeight]
  );

  if (permissionsLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (!hasPermission('query:execute')) {
    return (
      <Box sx={pageContentSx}>
        <Typography>You do not have access to the query console.</Typography>
      </Box>
    );
  }

  return (
    <Box
      sx={{ display: 'flex', height: 'calc(100vh - 64px)', overflow: 'hidden' }}
    >
      {/* Side panel (schema / history) */}
      <QueryConsoleSchemaPanel
        open={schemaPanelOpen}
        onToggle={handleSchemaPanelToggle}
        onQuerySelect={handleQuerySelect}
        onHistorySelect={handleHistorySelect}
        historyRefreshTrigger={historyRefreshTrigger}
      />

      {/* Main content */}
      <Box
        sx={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          ...pageContentSx,
          boxSizing: 'border-box',
          minWidth: 0,
          overflow: 'hidden'
        }}
      >
        {/* Graph panel — detail panel open by default in the console */}
        <Box sx={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>
          {submittedQuery ? (
            <CypherGraph
              cypher={submittedQuery}
              defaultDetailOpen
              fillHeight
              onQueryComplete={handleQueryComplete}
            />
          ) : (
            <Card
              sx={{
                height: '100%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}
            >
              <CardContent>
                <Typography
                  variant="body2"
                  color="text.secondary"
                  align="center"
                >
                  Run a query below to visualize the graph.
                </Typography>
              </CardContent>
            </Card>
          )}
        </Box>

        {/* Resize handle */}
        <Box
          onMouseDown={handleDragStart}
          sx={{
            height: 8,
            flexShrink: 0,
            cursor: 'ns-resize',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            my: 0.5,
            '&::after': {
              content: '""',
              display: 'block',
              width: 48,
              height: 4,
              borderRadius: 2,
              bgcolor: 'divider',
              transition: 'background-color 0.15s',
            },
            '&:hover::after': { bgcolor: 'primary.main' },
          }}
        />

        {/* Query editor */}
        <Box sx={{ height: queryHeight, flexShrink: 0 }}>
          <Card sx={{ height: '100%' }}>
            <CardContent
              sx={{
                height: '100%',
                boxSizing: 'border-box',
                display: 'flex',
                flexDirection: 'column',
                '&:last-child': { pb: 2 },
              }}
            >
              <TextField
                multiline
                fullWidth
                value={queryText}
                onChange={(e) => setQueryText(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Enter a Cypher query... (Ctrl+Enter to run)"
                variant="outlined"
                sx={{
                  flex: 1,
                  minHeight: 0,
                  '& .MuiInputBase-root': {
                    height: '100%',
                    alignItems: 'flex-start',
                  },
                  '& .MuiInputBase-input': {
                    height: '100% !important',
                    overflow: 'auto !important',
                    boxSizing: 'border-box',
                  },
                }}
                inputProps={{
                  style: { fontFamily: 'monospace', fontSize: 13 }
                }}
              />
              <Box
                sx={{
                  mt: 1,
                  display: 'flex',
                  justifyContent: 'flex-end',
                  flexShrink: 0,
                }}
              >
                <Button
                  variant="contained"
                  startIcon={<PlayArrow />}
                  onClick={handleRun}
                  disabled={!queryText.trim()}
                >
                  Run
                </Button>
              </Box>
            </CardContent>
          </Card>
        </Box>
      </Box>
    </Box>
  );
}
