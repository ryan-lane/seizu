import { useState } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
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
  ScheduledQueryVersion,
  useScheduledQueryVersionsList,
  useScheduledQueriesMutations
} from 'src/hooks/useScheduledQueriesApi';
import UserDisplay from 'src/components/UserDisplay';
import ScheduledQueryDetailDialog, {
  ScheduledQueryViewData
} from 'src/components/ScheduledQueryDetailDialog';
import { usePermissions } from 'src/hooks/usePermissions';
import type { BackState } from 'src/navigation';
import { pageContentSx } from 'src/theme/layout';

// ---------------------------------------------------------------------------
// Per-row overflow menu
// ---------------------------------------------------------------------------

interface RowMenuProps {
  version: ScheduledQueryVersion;
  isCurrent: boolean;
  onRestore: () => void;
}

function RowMenu({ version: _version, isCurrent, onRestore }: RowMenuProps) {
  const [anchor, setAnchor] = useState<null | HTMLElement>(null);
  const hasPermission = usePermissions();
  const close = () => setAnchor(null);

  const canWrite = hasPermission('scheduled_queries:write');
  const restoreDisabled = isCurrent || !canWrite;
  const restoreTooltip = isCurrent
    ? 'This is already the current version'
    : !canWrite
      ? 'You do not have permission to restore scheduled query versions'
      : '';

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
        <Tooltip title={restoreTooltip} placement="left">
          <span>
            <MenuItem
              onClick={() => { onRestore(); close(); }}
              disabled={restoreDisabled}
            >
              <ListItemIcon>
                <RestoreIcon fontSize="small" color={restoreDisabled ? 'disabled' : 'inherit'} />
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

function ScheduledQueryHistory() {
  const { id } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const { fromLabel } = (location.state ?? {}) as BackState;

  const { versions, loading, error } = useScheduledQueryVersionsList(id ?? null);
  const { updateScheduledQuery } = useScheduledQueriesMutations();
  const [detailData, setDetailData] = useState<ScheduledQueryViewData | null>(null);

  const sorted = [...versions].sort((a, b) => b.version - a.version);
  const latestVersion = sorted[0]?.version;
  const queryName = sorted[0]?.name;

  async function handleRestore(version: ScheduledQueryVersion) {
    if (!id) return;
    await updateScheduledQuery(id, {
      name: version.name,
      cypher: version.cypher,
      params: version.params,
      frequency: version.frequency,
      watch_scans: version.watch_scans,
      enabled: version.enabled,
      actions: version.actions,
      comment: `Restored from version ${version.version}`
    });
    navigate(`/app/scheduled-queries`);
  }

  return (
    <>
      <Helmet>
        <title>{queryName ? `History – ${queryName} | Seizu` : `History | Seizu`}</title>
      </Helmet>
      <Box sx={pageContentSx}>
        {fromLabel && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
            <Button
              size="small"
              startIcon={<ArrowBackIcon />}
              onClick={() => navigate(-1)}
            >
              Back to {fromLabel}
            </Button>
          </Box>
        )}

        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 3 }}>
          <HistoryIcon color="action" />
          <Typography variant="h1">
            Version history{queryName ? ` – ${queryName}` : ''}
          </Typography>
        </Box>

        {loading && (
          <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
            <CircularProgress />
          </Box>
        )}

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
                      <TableCell sx={{ fontWeight: isCurrent ? 'bold' : undefined }}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <Typography
                            fontWeight={isCurrent ? 'bold' : 'medium'}
                            sx={{ cursor: 'pointer', '&:hover': { textDecoration: 'underline' } }}
                            onClick={() => setDetailData({
                              name: v.name,
                              version: v.version,
                              cypher: v.cypher,
                              params: v.params,
                              frequency: v.frequency,
                              watch_scans: v.watch_scans,
                              enabled: v.enabled,
                              actions: v.actions,
                            })}
                          >
                            v{v.version}
                          </Typography>
                          {isCurrent && (
                            <Typography
                              component="span"
                              variant="caption"
                              color="primary"
                            >
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

      <ScheduledQueryDetailDialog
        open={!!detailData}
        onClose={() => setDetailData(null)}
        data={detailData}
      />
    </>
  );
}

export default ScheduledQueryHistory;
