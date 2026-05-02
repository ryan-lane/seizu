import { useState } from 'react';
import { useParams, useNavigate, useLocation, Link as RouterLink } from 'react-router-dom';
import { Helmet } from 'react-helmet';
import {
  Box,
  Button,
  CircularProgress,
  Divider,
  IconButton,
  Link,
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
import VisibilityIcon from '@mui/icons-material/Visibility';
import Error from '@mui/icons-material/Error';

import { ReportVersion, useReportVersionsList, useReportsMutations } from 'src/hooks/useReportsApi';
import { Report } from 'src/config.context';
import UserDisplay from 'src/components/UserDisplay';
import { usePermissions } from 'src/hooks/usePermissions';
import type { BackState } from 'src/navigation';
import { pageContentSx } from 'src/theme/layout';

// ---------------------------------------------------------------------------
// Per-row overflow menu
// ---------------------------------------------------------------------------

interface RowMenuProps {
  version: ReportVersion;
  isCurrent: boolean;
  onView: () => void;
  onRestore: () => void;
}

function RowMenu({ version: _version, isCurrent, onView, onRestore }: RowMenuProps) {
  const [anchor, setAnchor] = useState<null | HTMLElement>(null);
  const hasPermission = usePermissions();
  const close = () => setAnchor(null);

  const canWrite = hasPermission('reports:write');
  const restoreDisabled = isCurrent || !canWrite;
  const restoreTooltip = isCurrent
    ? 'This is already the current version'
    : !canWrite
      ? 'You do not have permission to restore report versions'
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
        <MenuItem onClick={() => { onView(); close(); }}>
          <ListItemIcon><VisibilityIcon fontSize="small" /></ListItemIcon>
          <ListItemText>View</ListItemText>
        </MenuItem>

        <Divider />

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

function ReportHistory() {
  const { id } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const { fromLabel } = (location.state ?? {}) as BackState;

  const { versions, loading, error } = useReportVersionsList(id);
  const { saveReportVersion } = useReportsMutations();

  const sorted = [...versions].sort((a, b) => b.version - a.version);
  const latestVersion = sorted[0]?.version;
  const reportName = sorted[0]?.name;

  async function handleRestore(version: ReportVersion) {
    if (!id) return;
    await saveReportVersion(
      id,
      version.config as Report,
      `Restored from version ${version.version}`
    );
    navigate(`/app/reports/${id}`);
  }

  return (
    <>
      <Helmet>
        <title>{reportName ? `History – ${reportName} | Seizu` : `History | Seizu`}</title>
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
            Version history{reportName ? ` – ${reportName}` : ''}
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
                  <TableCell>Author</TableCell>
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
                          <Link
                            component={RouterLink}
                            to={`/app/reports/${id}/versions/${v.version}`}
                            underline="hover"
                            color="inherit"
                            fontWeight={isCurrent ? 'bold' : 'medium'}
                          >
                            v{v.version}
                          </Link>
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
                      <TableCell sx={{ color: 'text.secondary' }}><UserDisplay userId={v.created_by} /></TableCell>
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
                          onView={() => navigate(`/app/reports/${id}/versions/${v.version}`, { state: { fromLabel: reportName ? `History – ${reportName}` : 'history' } satisfies BackState })}
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
    </>
  );
}

export default ReportHistory;
