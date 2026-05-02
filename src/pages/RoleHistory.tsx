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
  RoleVersion,
  isBuiltinRole,
  useRoleMutations,
  useRoleVersionsList
} from 'src/hooks/useRolesApi';
import UserDisplay from 'src/components/UserDisplay';
import { usePermissionState } from 'src/hooks/usePermissions';
import type { BackState } from 'src/navigation';
import { pageContentSx } from 'src/theme/layout';

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
  return (
    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
      {visible.map((permission) => (
        <Chip key={permission} label={permission} size="small" variant="outlined" />
      ))}
      {remaining > 0 && <Chip label={`+${remaining}`} size="small" variant="outlined" />}
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
          <TableContainer component={Paper} variant="outlined">
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Version</TableCell>
                  <TableCell>Saved</TableCell>
                  <TableCell>Created by</TableCell>
                  <TableCell>Permissions</TableCell>
                  <TableCell>Comment</TableCell>
                  <TableCell />
                </TableRow>
              </TableHead>
              <TableBody>
                {sorted.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={6}>
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
                          <Typography fontWeight={isCurrent ? 'bold' : 'medium'}>
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
                      <TableCell sx={{ minWidth: 260 }}>
                        {permissionSummary(v)}
                      </TableCell>
                      <TableCell sx={{ color: 'text.secondary' }}>
                        {v.comment ? (
                          <Tooltip title={v.comment}>
                            <span>
                              {v.comment.length > 60 ? `${v.comment.slice(0, 60)}...` : v.comment}
                            </span>
                          </Tooltip>
                        ) : (
                          <Typography component="span" color="text.disabled" variant="body2">
                            -
                          </Typography>
                        )}
                      </TableCell>
                      <TableCell align="right" sx={{ width: 48, pr: 1 }}>
                        <RowMenu
                          isCurrent={isCurrent}
                          hasPermission={hasPermission}
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

export default RoleHistory;
