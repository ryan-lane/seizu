import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Helmet } from 'react-helmet';
import {
  Box,
  Button,
  CircularProgress,
  IconButton,
  ListItemIcon,
  ListItemText,
  Menu,
  MenuItem,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tooltip,
  Typography
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import HistoryIcon from '@mui/icons-material/History';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import RestoreIcon from '@mui/icons-material/Restore';
import Error from '@mui/icons-material/Error';
import {
  ToolVersion,
  useToolVersionsList,
  useToolMutations
} from 'src/hooks/useToolsetsApi';
import ToolDetailDialog, { ToolViewData } from 'src/components/ToolDetailDialog';
import UserDisplay from 'src/components/UserDisplay';

// ---------------------------------------------------------------------------
// Per-row overflow menu
// ---------------------------------------------------------------------------

interface RowMenuProps {
  version: ToolVersion;
  isCurrent: boolean;
  onRestore: () => void;
  onDetail: () => void;
}

function RowMenu({ isCurrent, onRestore, onDetail }: RowMenuProps) {
  const [anchor, setAnchor] = useState<null | HTMLElement>(null);
  const close = () => setAnchor(null);

  return (
    <>
      <Tooltip title="More actions">
        <IconButton aria-label="More actions" size="small" onClick={(e) => setAnchor(e.currentTarget)}>
          <MoreVertIcon fontSize="small" />
        </IconButton>
      </Tooltip>

      <Menu
        anchorEl={anchor}
        open={!!anchor}
        onClose={close}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
        transformOrigin={{ vertical: 'top', horizontal: 'right' }}
        slotProps={{ paper: { sx: { minWidth: 180 } } }}
      >
        <MenuItem onClick={() => { onDetail(); close(); }}>
          <ListItemIcon><HistoryIcon fontSize="small" /></ListItemIcon>
          <ListItemText>View detail</ListItemText>
        </MenuItem>

        <Tooltip
          title={isCurrent ? 'This is already the current version' : ''}
          placement="left"
        >
          <span>
            <MenuItem onClick={() => { onRestore(); close(); }} disabled={isCurrent}>
              <ListItemIcon>
                <RestoreIcon fontSize="small" color={isCurrent ? 'disabled' : 'inherit'} />
              </ListItemIcon>
              <ListItemText>Restore</ListItemText>
            </MenuItem>
          </span>
        </Tooltip>
      </Menu>
    </>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

function ToolHistory() {
  const { toolsetId, toolId } = useParams();
  const navigate = useNavigate();

  const { versions, loading, error } = useToolVersionsList(toolsetId ?? null, toolId ?? null);
  const mutations = useToolMutations(toolsetId ?? '');
  const [detailData, setDetailData] = useState<ToolViewData | null>(null);

  const sorted = [...versions].sort((a, b) => b.version - a.version);
  const latestVersion = sorted[0]?.version;
  const toolName = sorted[0]?.name;

  async function handleRestore(version: ToolVersion) {
    if (!toolId) return;
    await mutations.updateTool(toolId, {
      name: version.name,
      description: version.description,
      cypher: version.cypher,
      parameters: version.parameters,
      enabled: version.enabled,
      comment: `Restored from version ${version.version}`
    });
    navigate(`/app/toolsets/${toolsetId}/tools`);
  }

  return (
    <>
      <Helmet>
        <title>{toolName ? `History – ${toolName} | Seizu` : 'History | Seizu'}</title>
      </Helmet>
      <Box sx={{ p: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
          <Button
            size="small"
            startIcon={<ArrowBackIcon />}
            onClick={() => navigate(`/app/toolsets/${toolsetId}/tools`)}
          >
            Back to tools
          </Button>
        </Box>

        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 3 }}>
          <HistoryIcon color="action" />
          <Typography variant="h1">
            Version history{toolName ? ` – ${toolName}` : ''}
          </Typography>
        </Box>

        {loading && <CircularProgress />}

        {error && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Error />
            <Typography>Failed to load version history</Typography>
          </Box>
        )}

        {!loading && !error && (
          <TableContainer component={Paper} variant="outlined">
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Version</TableCell>
                  <TableCell>Saved</TableCell>
                  <TableCell>Created by</TableCell>
                  <TableCell>Comment</TableCell>
                  <TableCell />
                </TableRow>
              </TableHead>
              <TableBody>
                {sorted.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={5}>
                      <Typography color="text.secondary" sx={{ py: 1 }}>
                        No versions found.
                      </Typography>
                    </TableCell>
                  </TableRow>
                )}
                {sorted.map((v) => {
                  const isCurrent = v.version === latestVersion;
                  return (
                    <TableRow key={v.version} hover>
                      <TableCell>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <Typography
                            fontWeight={isCurrent ? 'bold' : 'medium'}
                            sx={{ cursor: 'pointer', '&:hover': { textDecoration: 'underline' } }}
                            onClick={() =>
                              setDetailData({
                                name: v.name,
                                version: v.version,
                                description: v.description,
                                cypher: v.cypher,
                                parameters: v.parameters,
                                enabled: v.enabled
                              })
                            }
                          >
                            v{v.version}
                          </Typography>
                          {isCurrent && (
                            <Typography component="span" variant="caption" color="primary">
                              current
                            </Typography>
                          )}
                        </Box>
                      </TableCell>
                      <TableCell sx={{ color: 'text.secondary', whiteSpace: 'nowrap' }}>
                        {new Date(v.created_at).toLocaleString()}
                      </TableCell>
                      <TableCell sx={{ color: 'text.secondary' }}>
                        <UserDisplay userId={v.created_by} />
                      </TableCell>
                      <TableCell sx={{ color: 'text.secondary' }}>
                        {v.comment ? (
                          <Tooltip title={v.comment}>
                            <span>
                              {v.comment.length > 60 ? `${v.comment.slice(0, 60)}…` : v.comment}
                            </span>
                          </Tooltip>
                        ) : (
                          <Typography component="span" color="text.disabled" variant="body2">
                            —
                          </Typography>
                        )}
                      </TableCell>
                      <TableCell align="right" sx={{ width: 48, pr: 1 }}>
                        <RowMenu
                          version={v}
                          isCurrent={isCurrent}
                          onRestore={() => handleRestore(v)}
                          onDetail={() =>
                            setDetailData({
                              name: v.name,
                              version: v.version,
                              description: v.description,
                              cypher: v.cypher,
                              parameters: v.parameters,
                              enabled: v.enabled
                            })
                          }
                        />
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Box>

      <ToolDetailDialog
        open={!!detailData}
        onClose={() => setDetailData(null)}
        data={detailData}
      />
    </>
  );
}

export default ToolHistory;
