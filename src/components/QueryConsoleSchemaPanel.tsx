import { useEffect, useState } from 'react';
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Box,
  IconButton,
  List,
  ListItemButton,
  Tooltip,
  Typography
} from '@mui/material';
import { useTheme } from '@mui/material/styles';
import AccountTree from '@mui/icons-material/AccountTree';
import ChevronLeft from '@mui/icons-material/ChevronLeft';
import ExpandMore from '@mui/icons-material/ExpandMore';
import History from '@mui/icons-material/History';
import { useLazyCypherQuery } from 'src/hooks/useCypherQuery';
import { colorForGroup } from 'src/components/reports/CypherGraph';
import QueryConsoleHistoryPanel from 'src/components/QueryConsoleHistoryPanel';

const LABELS_QUERY = 'CALL db.labels() YIELD label RETURN label ORDER BY label';
const RELS_QUERY =
  'CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType AS type ORDER BY type';
const PROPS_QUERY =
  'CALL db.propertyKeys() YIELD propertyKey RETURN propertyKey AS key ORDER BY key';

const PANEL_WIDTH = 260;

type ActiveTab = 'schema' | 'history';

interface QueryConsoleSchemaProps {
  open: boolean;
  onToggle: (tab?: ActiveTab) => void;
  onQuerySelect: (query: string) => void;
  onHistorySelect: (query: string) => void;
  historyRefreshTrigger?: number;
}

export default function QueryConsoleSchemaPanel({
  open,
  onToggle,
  onQuerySelect,
  onHistorySelect,
  historyRefreshTrigger
}: QueryConsoleSchemaProps) {
  const theme = useTheme();
  const [activeTab, setActiveTab] = useState<ActiveTab>('schema');

  const [runLabels, { records: labelRecords }] =
    useLazyCypherQuery(LABELS_QUERY);
  const [runRels, { records: relRecords }] = useLazyCypherQuery(RELS_QUERY);
  const [runProps, { records: propRecords }] = useLazyCypherQuery(PROPS_QUERY);

  useEffect(() => {
    runLabels();
    runRels();
    runProps();
  }, [runLabels, runRels, runProps]);

  const labels =
    labelRecords?.map((r) => String(r.label)).filter(Boolean) ?? [];
  const rels = relRecords?.map((r) => String(r.type)).filter(Boolean) ?? [];
  const props = propRecords?.map((r) => String(r.key)).filter(Boolean) ?? [];

  /** Open or switch to a tab. If already open on the same tab, collapse. */
  const handleTabClick = (tab: ActiveTab) => {
    if (open && activeTab === tab) {
      onToggle();
    } else {
      setActiveTab(tab);
      if (!open) onToggle(tab);
    }
  };

  return (
    <Box
      sx={{
        width: open ? PANEL_WIDTH : 40,
        height: '100%',
        flexShrink: 0,
        borderRight: 1,
        borderColor: 'divider',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        transition: 'width 0.2s ease'
      }}
    >
      {/* Header / toggle */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: open ? 'space-between' : 'center',
          px: open ? 1.5 : 0,
          minHeight: 40,
          borderBottom: 1,
          borderColor: 'divider',
          flexShrink: 0
        }}
      >
        {open ? (
          <>
            <Typography
              variant="caption"
              sx={{
                fontWeight: 700,
                letterSpacing: 0.8,
                color: 'text.secondary'
              }}
            >
              {activeTab === 'schema' ? 'DATABASE' : 'HISTORY'}
            </Typography>
            <Box sx={{ display: 'flex', alignItems: 'center' }}>
              <Tooltip title="Database schema" placement="right">
                <IconButton
                  size="small"
                  onClick={() => handleTabClick('schema')}
                  color={activeTab === 'schema' ? 'primary' : 'default'}
                >
                  <AccountTree fontSize="small" />
                </IconButton>
              </Tooltip>
              <Tooltip title="Query history" placement="right">
                <IconButton
                  size="small"
                  onClick={() => handleTabClick('history')}
                  color={activeTab === 'history' ? 'primary' : 'default'}
                >
                  <History fontSize="small" />
                </IconButton>
              </Tooltip>
              <Tooltip title="Collapse" placement="right">
                <IconButton size="small" onClick={() => onToggle()}>
                  <ChevronLeft fontSize="small" />
                </IconButton>
              </Tooltip>
            </Box>
          </>
        ) : (
          <Box
            sx={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: 0.5
            }}
          >
            <Tooltip title="Database schema" placement="right">
              <IconButton size="small" onClick={() => handleTabClick('schema')}>
                <AccountTree fontSize="small" />
              </IconButton>
            </Tooltip>
            <Tooltip title="Query history" placement="right">
              <IconButton
                size="small"
                onClick={() => handleTabClick('history')}
              >
                <History fontSize="small" />
              </IconButton>
            </Tooltip>
          </Box>
        )}
      </Box>

      {/* Scrollable content */}
      {open && (
        <Box
          sx={{
            flex: 1,
            minHeight: 0,
            overflow: activeTab === 'history' ? 'hidden' : 'auto'
          }}
        >
          {activeTab === 'schema' ? (
            <>
              {/* ── Nodes ─────────────────────────────────────────── */}
              <Accordion
                defaultExpanded
                disableGutters
                elevation={0}
                square
                sx={{ '&:before': { display: 'none' } }}
              >
                <AccordionSummary
                  expandIcon={<ExpandMore fontSize="small" />}
                  sx={{
                    minHeight: 36,
                    px: 1.5,
                    '& .MuiAccordionSummary-content': { my: 0.5 }
                  }}
                >
                  <Typography
                    variant="caption"
                    sx={{ fontWeight: 700, letterSpacing: 0.5 }}
                  >
                    NODES{labels.length > 0 && ` (${labels.length})`}
                  </Typography>
                </AccordionSummary>
                <AccordionDetails sx={{ p: 0 }}>
                  <List dense disablePadding>
                    {labels.map((label) => (
                      <ListItemButton
                        key={label}
                        onClick={() =>
                          onQuerySelect(
                            `MATCH path = (n:\`${label}\`)-[r]-(m) RETURN path LIMIT 25`
                          )
                        }
                        sx={{ py: 0.5, px: 1.5 }}
                      >
                        {/* Styled like graph nodes: filled circle */}
                        <Box
                          sx={{
                            width: 14,
                            height: 14,
                            borderRadius: '50%',
                            bgcolor: colorForGroup(label),
                            flexShrink: 0,
                            mr: 1,
                            border: `2px solid ${theme.palette.background.paper}`,
                            boxShadow: `0 0 0 1px ${colorForGroup(label)}`
                          }}
                        />
                        <Typography variant="body2" noWrap>
                          {label}
                        </Typography>
                      </ListItemButton>
                    ))}
                  </List>
                </AccordionDetails>
              </Accordion>

              {/* ── Relationships ──────────────────────────────────── */}
              <Accordion
                defaultExpanded
                disableGutters
                elevation={0}
                square
                sx={{
                  '&:before': { display: 'none' },
                  borderTop: 1,
                  borderColor: 'divider'
                }}
              >
                <AccordionSummary
                  expandIcon={<ExpandMore fontSize="small" />}
                  sx={{
                    minHeight: 36,
                    px: 1.5,
                    '& .MuiAccordionSummary-content': { my: 0.5 }
                  }}
                >
                  <Typography
                    variant="caption"
                    sx={{ fontWeight: 700, letterSpacing: 0.5 }}
                  >
                    RELATIONSHIPS{rels.length > 0 && ` (${rels.length})`}
                  </Typography>
                </AccordionSummary>
                <AccordionDetails sx={{ p: 0 }}>
                  <List dense disablePadding>
                    {rels.map((type) => (
                      <ListItemButton
                        key={type}
                        onClick={() =>
                          onQuerySelect(
                            `MATCH path = (a)-[r:\`${type}\`]->(b) RETURN path LIMIT 25`
                          )
                        }
                        sx={{ py: 0.75, px: 1.5 }}
                      >
                        {/* ──[TYPE]──► */}
                        <Box
                          sx={{
                            display: 'flex',
                            alignItems: 'center',
                            minWidth: 0
                          }}
                        >
                          <Box
                            sx={{
                              width: 10,
                              height: 1.5,
                              bgcolor: 'text.disabled',
                              flexShrink: 0
                            }}
                          />
                          <Box
                            sx={{
                              border: 1,
                              borderColor: 'text.secondary',
                              borderRadius: 0.5,
                              px: 0.75,
                              lineHeight: '18px',
                              fontSize: 10,
                              fontFamily: 'monospace',
                              color: 'text.secondary',
                              whiteSpace: 'nowrap',
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              maxWidth: 160,
                              flexShrink: 1
                            }}
                          >
                            {type}
                          </Box>
                          <Box
                            sx={{
                              width: 10,
                              height: 1.5,
                              bgcolor: 'text.disabled',
                              flexShrink: 0
                            }}
                          />
                          {/* arrowhead */}
                          <Box
                            sx={{
                              width: 0,
                              height: 0,
                              borderTop: '4px solid transparent',
                              borderBottom: '4px solid transparent',
                              borderLeft: `5px solid ${theme.palette.text.disabled}`,
                              flexShrink: 0
                            }}
                          />
                        </Box>
                      </ListItemButton>
                    ))}
                  </List>
                </AccordionDetails>
              </Accordion>

              {/* ── Property keys ──────────────────────────────────── */}
              <Accordion
                defaultExpanded
                disableGutters
                elevation={0}
                square
                sx={{
                  '&:before': { display: 'none' },
                  borderTop: 1,
                  borderColor: 'divider'
                }}
              >
                <AccordionSummary
                  expandIcon={<ExpandMore fontSize="small" />}
                  sx={{
                    minHeight: 36,
                    px: 1.5,
                    '& .MuiAccordionSummary-content': { my: 0.5 }
                  }}
                >
                  <Typography
                    variant="caption"
                    sx={{ fontWeight: 700, letterSpacing: 0.5 }}
                  >
                    PROPERTY KEYS{props.length > 0 && ` (${props.length})`}
                  </Typography>
                </AccordionSummary>
                <AccordionDetails sx={{ p: 0 }}>
                  <List dense disablePadding>
                    {props.map((key) => (
                      <ListItemButton
                        key={key}
                        onClick={() =>
                          onQuerySelect(
                            `MATCH (n) WHERE n.\`${key}\` IS NOT NULL RETURN n LIMIT 25`
                          )
                        }
                        sx={{ py: 0.5, px: 1.5 }}
                      >
                        <Typography
                          variant="body2"
                          noWrap
                          sx={{
                            fontFamily: 'monospace',
                            fontSize: 12,
                            color: 'text.secondary'
                          }}
                        >
                          # {key}
                        </Typography>
                      </ListItemButton>
                    ))}
                  </List>
                </AccordionDetails>
              </Accordion>
            </>
          ) : (
            <QueryConsoleHistoryPanel
              onQuerySelect={onHistorySelect}
              refreshTrigger={historyRefreshTrigger}
            />
          )}
        </Box>
      )}
    </Box>
  );
}
