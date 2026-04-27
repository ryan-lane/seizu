import { useCallback, useState } from 'react';
import {
  Box,
  Button,
  Card,
  CardContent,
  TextField,
  Typography
} from '@mui/material';
import PlayArrow from '@mui/icons-material/PlayArrow';
import CypherGraph from 'src/components/reports/CypherGraph';
import QueryConsoleSchemaPanel from 'src/components/QueryConsoleSchemaPanel';
import { usePermissions } from 'src/hooks/usePermissions';

export default function QueryConsole() {
  const hasPermission = usePermissions();
  const [queryText, setQueryText] = useState('');
  const [submittedQuery, setSubmittedQuery] = useState<string | undefined>(
    undefined
  );
  const [schemaPanelOpen, setSchemaPanelOpen] = useState(true);
  const [historyRefreshTrigger, setHistoryRefreshTrigger] = useState(0);

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

  if (!hasPermission('query:execute')) {
    return (
      <Box sx={{ p: 3 }}>
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
        onToggle={() => setSchemaPanelOpen((v) => !v)}
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
          p: 3,
          gap: 2,
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

        {/* Query editor */}
        <Box sx={{ flexShrink: 0 }}>
          <Card>
            <CardContent>
              <TextField
                multiline
                rows={5}
                fullWidth
                value={queryText}
                onChange={(e) => setQueryText(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Enter a Cypher query... (Ctrl+Enter to run)"
                variant="outlined"
                inputProps={{
                  style: { fontFamily: 'monospace', fontSize: 13 }
                }}
              />
              <Box sx={{ mt: 1, display: 'flex', justifyContent: 'flex-end' }}>
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
