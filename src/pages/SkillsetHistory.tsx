import { useState } from 'react';
import {
  Box,
  Button,
  ButtonBase,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
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
import { useNavigate, useLocation, useParams } from 'react-router-dom';
import { Helmet } from 'react-helmet';
import {
  SkillsetVersion,
  useSkillsetMutations,
  useSkillsetVersionsList
} from 'src/hooks/useSkillsetsApi';
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
const commentColumnSx = { ...listTableSecondaryCellSx, width: '28%' };

interface RowMenuProps {
  isCurrent: boolean;
  onRestore: () => void;
}

function RowMenu({ isCurrent, onRestore }: RowMenuProps) {
  const [anchor, setAnchor] = useState<null | HTMLElement>(null);
  const hasPermission = usePermissions();
  const canWrite = hasPermission('skillsets:write');
  const restoreDisabled = isCurrent || !canWrite;
  const restoreTooltip = isCurrent
    ? 'This is already the current version'
    : !canWrite
      ? 'You do not have permission to restore skillset versions'
      : '';
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
        <Tooltip title={restoreTooltip} placement="left">
          <span>
            <MenuItem onClick={() => { onRestore(); close(); }} disabled={restoreDisabled}>
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

function SkillsetVersionDetailDialog({
  version,
  onClose
}: {
  version: SkillsetVersion | null;
  onClose: () => void;
}) {
  if (!version) return null;

  return (
    <Dialog open onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>{version.name}</DialogTitle>
      <DialogContent dividers>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <Box>
            <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 0.5 }}>Version</Typography>
            <Typography variant="body2">v{version.version}</Typography>
          </Box>
          <Box>
            <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 0.5 }}>Status</Typography>
            <Chip label={version.enabled ? 'Enabled' : 'Disabled'} color={version.enabled ? 'success' : 'default'} size="small" />
          </Box>
          {version.description && (
            <Box>
              <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 0.5 }}>Description</Typography>
              <Typography variant="body2">{version.description}</Typography>
            </Box>
          )}
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  );
}

function SkillsetHistory() {
  const { skillsetId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const { fromLabel } = (location.state ?? {}) as BackState;
  const { versions, loading, error } = useSkillsetVersionsList(skillsetId ?? null);
  const { updateSkillset } = useSkillsetMutations();
  const [detailVersion, setDetailVersion] = useState<SkillsetVersion | null>(null);
  const sorted = [...versions].sort((a, b) => b.version - a.version);
  const latestVersion = sorted[0]?.version;
  const name = sorted[0]?.name;
  const columns: ListTableColumn<SkillsetVersion>[] = [
    {
      key: 'version',
      label: 'Version',
      cellSx: { width: 120 },
      render: (version) => {
        const isCurrent = version.version === latestVersion;
        return (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <ButtonBase
              onClick={() => setDetailVersion(version)}
              sx={{
                font: 'inherit',
                fontWeight: isCurrent ? 'bold' : 'medium',
                color: 'inherit',
                borderRadius: 0,
                textAlign: 'left',
                '&:hover': { textDecoration: 'underline' }
              }}
            >
              <Typography component="span" sx={{ lineHeight: 1.4 }}>
                v{version.version}
              </Typography>
            </ButtonBase>
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
      key: 'name',
      label: 'Name',
      cellSx: { width: '24%' },
      render: (version) => version.name
    },
    {
      key: 'saved',
      label: 'Saved',
      hideBelow: 'sm',
      cellSx: savedColumnSx,
      render: (version) => new Date(version.created_at).toLocaleString()
    },
    {
      key: 'created_by',
      label: 'Created By',
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
          isCurrent={version.version === latestVersion}
          onRestore={() => handleRestore(version)}
        />
      )
    }
  ];

  async function handleRestore(version: SkillsetVersion) {
    if (!skillsetId) return;
    await updateSkillset(skillsetId, {
      name: version.name,
      description: version.description,
      enabled: version.enabled,
      comment: `Restored from version ${version.version}`
    });
    navigate('/app/skillsets');
  }

  return (
    <Box sx={pageContentSx}>
      <Helmet><title>{name ? `History - ${name} | Seizu` : 'History | Seizu'}</title></Helmet>
      {fromLabel && <Button startIcon={<ArrowBackIcon />} onClick={() => navigate(-1)} sx={{ mb: 2 }}>Back to {fromLabel}</Button>}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 3 }}>
        <HistoryIcon color="action" /><Typography variant="h1">Version history{name ? ` - ${name}` : ''}</Typography>
      </Box>
      {loading && <CircularProgress />}
      {error && <Typography color="error">Failed to load history</Typography>}
      {!loading && !error && (
        <ListTable
          rows={sorted}
          columns={columns}
          getRowKey={(version) => version.version}
          emptyMessage="No versions found."
          pagination={false}
        />
      )}
      <SkillsetVersionDetailDialog
        version={detailVersion}
        onClose={() => setDetailVersion(null)}
      />
    </Box>
  );
}

export default SkillsetHistory;
