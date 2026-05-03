import { useState } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { Helmet } from 'react-helmet';
import {
  Box,
  Button,
  Chip,
  CircularProgress,
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
import Error from '@mui/icons-material/Error';
import {
  RoleVersion,
  isBuiltinRole,
  useRoleMutations,
  useRoleVersionsList
} from 'src/hooks/useRolesApi';
import ListTable, {
  ListTableColumn,
  listTableActionColumnSx,
  listTableSecondaryCellSx
} from 'src/components/ListTable';
import UserDisplay from 'src/components/UserDisplay';
import { usePermissionState } from 'src/hooks/usePermissions';
import type { BackState } from 'src/navigation';
import { pageContentSx } from 'src/theme/layout';

const savedColumnSx = { ...listTableSecondaryCellSx, width: 180 };
const authorColumnSx = { ...listTableSecondaryCellSx, width: 150 };
const permissionsColumnSx = { width: '28%' };
const commentColumnSx = { ...listTableSecondaryCellSx, width: '24%' };

interface RowMenuProps {
  isCurrent: boolean;
  hasPermission: (permission: string) => boolean;
  onRestore: () => void;
}

function RowMenu({ isCurrent, hasPermission, onRestore }: RowMenuProps) {
  const [anchor, setAnchor] = useState<null | HTMLElement>(null);
  const close = () => setAnchor(null);

  const canWrite = hasPermission('roles:write');
  const restoreDisabled = isCurrent || !canWrite;
  const restoreTooltip = isCurrent
    ? 'This is already the current version'
    : !canWrite
      ? 'You do not have permission to restore role versions'
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

function permissionSummary(version: RoleVersion) {
  const visible = version.permissions.slice(0, 4);
  const remaining = version.permissions.length - visible.length;
  const hidden = version.permissions.slice(visible.length);
  return (
    <Box sx={{ display: 'flex', flexWrap: 'nowrap', gap: 0.5, overflow: 'hidden' }}>
      {visible.map((permission) => (
        <Chip key={permission} label={permission} size="small" variant="outlined" />
      ))}
      {remaining > 0 && (
        <Tooltip
          title={
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5, py: 0.5 }}>
              {hidden.map((permission) => (
                <Typography key={permission} variant="body2">
                  {permission}
                </Typography>
              ))}
            </Box>
          }
          placement="top"
        >
          <Chip label={`+${remaining}`} size="small" variant="outlined" />
        </Tooltip>
      )}
    </Box>
  );
}

function RoleHistory() {
  const { roleId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const { fromLabel } = (location.state ?? {}) as BackState;
  const { hasPermission, loading: permissionsLoading } = usePermissionState();
  const canRead = hasPermission('roles:read');
  const builtin = !!roleId && isBuiltinRole(roleId);

  const { versions, loading, error } = useRoleVersionsList(roleId ?? null, canRead && !builtin);
  const { updateRole } = useRoleMutations();

  const sorted = [...versions].sort((a, b) => b.version - a.version);
  const latestVersion = sorted[0]?.version;
  const roleName = sorted[0]?.name;
  const columns: ListTableColumn<RoleVersion>[] = [
    {
      key: 'version',
      label: 'Version',
      cellSx: { width: 120 },
      render: (version) => {
        const isCurrent = version.version === latestVersion;
        return (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Typography fontWeight={isCurrent ? 'bold' : 'medium'}>
              v{version.version}
            </Typography>
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
      key: 'created_by',
      label: 'Created by',
      hideBelow: 'md',
      cellSx: authorColumnSx,
      render: (version) => <UserDisplay userId={version.created_by} />
    },
    {
      key: 'permissions',
      label: 'Permissions',
      hideBelow: 'lg',
      cellSx: permissionsColumnSx,
      render: (version) => permissionSummary(version)
    },
    {
      key: 'comment',
      label: 'Comment',
      hideBelow: 'xl',
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
          hasPermission={hasPermission}
          onRestore={() => handleRestore(version)}
        />
      )
    }
  ];

  async function handleRestore(version: RoleVersion) {
    if (!roleId) return;
    await updateRole(roleId, {
      name: version.name,
      description: version.description,
      permissions: version.permissions,
      comment: `Restored from version ${version.version}`
    });
    navigate('/app/roles');
  }

  if (permissionsLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (!canRead) {
    return (
      <Box sx={pageContentSx}>
        <Typography>You do not have access to role management.</Typography>
      </Box>
    );
  }

  if (builtin) {
    return (
      <Box sx={pageContentSx}>
        <Button
          size="small"
          startIcon={<ArrowBackIcon />}
          onClick={() => navigate('/app/roles')}
          sx={{ mb: 2 }}
        >
          Back to roles
        </Button>
        <Typography>Built-in roles do not have version history.</Typography>
      </Box>
    );
  }

  return (
    <>
      <Helmet>
        <title>{roleName ? `History - ${roleName} | Seizu` : 'History | Seizu'}</title>
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
            Version history{roleName ? ` - ${roleName}` : ''}
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

export default RoleHistory;
