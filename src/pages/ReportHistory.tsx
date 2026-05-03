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
import ListTable, {
  ListTableColumn,
  listTableActionColumnSx,
  listTableSecondaryCellSx
} from 'src/components/ListTable';
import UserDisplay from 'src/components/UserDisplay';
import { usePermissions } from 'src/hooks/usePermissions';
import type { BackState } from 'src/navigation';
import { pageContentSx } from 'src/theme/layout';

const savedColumnSx = { ...listTableSecondaryCellSx, width: 180 };
const authorColumnSx = { ...listTableSecondaryCellSx, width: 150 };
const commentColumnSx = { ...listTableSecondaryCellSx, width: '34%' };

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
  const { fromLabel, originReturnTo } = (location.state ?? {}) as BackState;

  const { versions, loading, error } = useReportVersionsList(id);
  const { saveReportVersion } = useReportsMutations();

  const sorted = [...versions].sort((a, b) => b.version - a.version);
  const latestVersion = sorted[0]?.version;
  const reportName = sorted[0]?.name;
  const historyBackTarget = originReturnTo ?? `/app/reports/${id}`;
  const versionBackState = {
    fromLabel: reportName ? `History – ${reportName}` : 'history',
    returnTo: `/app/reports/${id}/history`,
    originReturnTo: historyBackTarget
  } satisfies BackState;
  const columns: ListTableColumn<ReportVersion>[] = [
    {
      key: 'version',
      label: 'Version',
      cellSx: { width: 120 },
      render: (version) => {
        const isCurrent = version.version === latestVersion;
        return (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Link
            component={RouterLink}
            to={`/app/reports/${id}/versions/${version.version}`}
            state={versionBackState}
            underline="hover"
            color="inherit"
            fontWeight={isCurrent ? 'bold' : 'medium'}
          >
              v{version.version}
            </Link>
            {isCurrent && (
              <Typography component="span" variant="caption" color="primary">
                current
              </Typography>
            )}
          </Box>
        );
      }
    },
    {
      key: 'saved',
      label: 'Saved',
      hideBelow: 'sm',
      cellSx: savedColumnSx,
      render: (version) => new Date(version.created_at).toLocaleString()
    },
    {
      key: 'author',
      label: 'Author',
      hideBelow: 'md',
      cellSx: authorColumnSx,
      render: (version) => <UserDisplay userId={version.created_by} />
    },
    {
      key: 'comment',
      label: 'Comment',
      hideBelow: 'lg',
      cellSx: commentColumnSx,
      render: (version) => version.comment || '—'
    },
    {
      key: 'actions',
      align: 'right',
      cellSx: listTableActionColumnSx,
      render: (version) => (
        <RowMenu
          version={version}
          isCurrent={version.version === latestVersion}
          onView={() => navigate(`/app/reports/${id}/versions/${version.version}`, { state: versionBackState })}
          onRestore={() => handleRestore(version)}
        />
      )
    }
  ];

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
              onClick={() => navigate(historyBackTarget)}
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
          <ListTable
            rows={sorted}
            columns={columns}
            getRowKey={(version) => version.version}
            emptyMessage="No versions found."
            pagination={false}
          />
        )}
      </Box>
    </>
  );
}

export default ReportHistory;
