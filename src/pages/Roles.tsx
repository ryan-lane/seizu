import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Alert,
  Box,
  Button,
  Checkbox,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  Divider,
  FormControlLabel,
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
  TextField,
  Tooltip,
  Typography
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import EditIcon from '@mui/icons-material/Edit';
import HistoryIcon from '@mui/icons-material/History';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import VisibilityIcon from '@mui/icons-material/Visibility';
import Error from '@mui/icons-material/Error';
import {
  CreateRoleRequest,
  RoleItem,
  UpdateRoleRequest,
  isBuiltinRole,
  useBuiltinRolesList,
  useRoleMutations,
  useRolesList
} from 'src/hooks/useRolesApi';
import UserDisplay from 'src/components/UserDisplay';
import { usePermissions } from 'src/hooks/usePermissions';

function permissionGroup(permission: string): string {
  return permission.split(':')[0] || 'other';
}

function groupedPermissions(permissions: string[]): Record<string, string[]> {
  return permissions
    .slice()
    .sort()
    .reduce<Record<string, string[]>>((acc, permission) => {
      const group = permissionGroup(permission);
      acc[group] = [...(acc[group] ?? []), permission];
      return acc;
    }, {});
}

function permissionLabel(group: string): string {
  return group.replace(/_/g, ' ');
}

interface RoleDetailDialogProps {
  role: RoleItem | null;
  onClose: () => void;
}

function RoleDetailDialog({ role, onClose }: RoleDetailDialogProps) {
  const groups = useMemo(
    () => groupedPermissions(role?.permissions ?? []),
    [role]
  );

  return (
    <Dialog open={!!role} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>{role?.name ?? 'Role details'}</DialogTitle>
      <DialogContent dividers>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <Box>
            <Typography variant="subtitle2" color="text.secondary">
              Description
            </Typography>
            <Typography>{role?.description || '-'}</Typography>
          </Box>
          <Box>
            <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 1 }}>
              Permissions
            </Typography>
            {Object.keys(groups).length === 0 ? (
              <Typography color="text.secondary">No permissions.</Typography>
            ) : (
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                {Object.entries(groups).map(([group, permissions]) => (
                  <Box key={group}>
                    <Typography variant="body2" fontWeight={700} sx={{ textTransform: 'capitalize', mb: 0.75 }}>
                      {permissionLabel(group)}
                    </Typography>
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75 }}>
                      {permissions.map((permission) => (
                        <Chip key={permission} label={permission} size="small" variant="outlined" />
                      ))}
                    </Box>
                  </Box>
                ))}
              </Box>
            )}
          </Box>
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  );
}

interface RoleDialogProps {
  open: boolean;
  onClose: () => void;
  onSave: (req: CreateRoleRequest | UpdateRoleRequest) => Promise<void>;
  initial: RoleItem | null;
  availablePermissions: string[];
}

function RoleDialog({ open, onClose, onSave, initial, availablePermissions }: RoleDialogProps) {
  const [name, setName] = useState(initial?.name ?? '');
  const [description, setDescription] = useState(initial?.description ?? '');
  const [permissions, setPermissions] = useState<string[]>(initial?.permissions ?? []);
  const [comment, setComment] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const groups = useMemo(
    () => groupedPermissions(availablePermissions),
    [availablePermissions]
  );

  const handleClose = () => {
    setError(null);
    onClose();
  };

  const togglePermission = (permission: string) => {
    setPermissions((current) => (
      current.includes(permission)
        ? current.filter((p) => p !== permission)
        : [...current, permission].sort()
    ));
  };

  const handleSave = async () => {
    setError(null);
    if (!name.trim()) {
      setError('Name is required.');
      return;
    }
    if (permissions.length === 0) {
      setError('Select at least one permission.');
      return;
    }

    const req = initial
      ? {
          name: name.trim(),
          description: description.trim(),
          permissions,
          comment: comment.trim() || null
        } as UpdateRoleRequest
      : {
          name: name.trim(),
          description: description.trim(),
          permissions
        } as CreateRoleRequest;

    setSaving(true);
    try {
      await onSave(req);
      handleClose();
    } catch (err) {
      setError((err as Error)?.message ?? 'Failed to save role.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="md" fullWidth>
      <DialogTitle>{initial ? 'Edit Role' : 'New Role'}</DialogTitle>
      <DialogContent dividers>
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <TextField
            label="Name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            fullWidth
            required
          />
          <TextField
            label="Description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            fullWidth
            multiline
            minRows={2}
          />
          <Box>
            <Typography variant="subtitle2" sx={{ mb: 1 }}>
              Permissions
            </Typography>
            {Object.keys(groups).length === 0 ? (
              <Typography color="text.secondary">
                No permissions are available from built-in role definitions.
              </Typography>
            ) : (
              <Box
                sx={{
                  display: 'grid',
                  gridTemplateColumns: { xs: '1fr', md: 'repeat(2, minmax(0, 1fr))' },
                  gap: 2
                }}
              >
                {Object.entries(groups).map(([group, groupPermissions]) => (
                  <Paper key={group} variant="outlined" sx={{ p: 1.5 }}>
                    <Typography variant="body2" fontWeight={700} sx={{ textTransform: 'capitalize', mb: 0.5 }}>
                      {permissionLabel(group)}
                    </Typography>
                    <Box sx={{ display: 'flex', flexDirection: 'column' }}>
                      {groupPermissions.map((permission) => (
                        <FormControlLabel
                          key={permission}
                          control={
                            <Checkbox
                              checked={permissions.includes(permission)}
                              onChange={() => togglePermission(permission)}
                            />
                          }
                          label={permission}
                        />
                      ))}
                    </Box>
                  </Paper>
                ))}
              </Box>
            )}
          </Box>
          {initial && (
            <TextField
              label="Comment (optional)"
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              fullWidth
              size="small"
              placeholder="Describe what changed..."
            />
          )}
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose} disabled={saving}>
          Cancel
        </Button>
        <Button onClick={handleSave} variant="contained" disabled={saving}>
          {saving ? <CircularProgress size={20} /> : 'Save'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

interface RowMenuProps {
  isBuiltin: boolean;
  onView: () => void;
  onEdit: () => void;
  onHistory: () => void;
  onDelete: () => void;
}

function RowMenu({ isBuiltin, onView, onEdit, onHistory, onDelete }: RowMenuProps) {
  const [anchor, setAnchor] = useState<null | HTMLElement>(null);
  const hasPermission = usePermissions();
  const close = () => setAnchor(null);

  const canWrite = hasPermission('roles:write');
  const canDelete = hasPermission('roles:delete');
  const editDisabled = isBuiltin || !canWrite;
  const deleteDisabled = isBuiltin || !canDelete;
  const historyDisabled = isBuiltin;
  const editTooltip = isBuiltin ? 'Built-in roles cannot be edited' : !canWrite ? 'You do not have permission to edit roles' : '';
  const deleteTooltip = isBuiltin ? 'Built-in roles cannot be deleted' : !canDelete ? 'You do not have permission to delete roles' : '';
  const historyTooltip = isBuiltin ? 'Built-in roles have no version history' : '';

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
        slotProps={{ paper: { sx: { minWidth: 190 } } }}
      >
        <MenuItem onClick={() => { onView(); close(); }}>
          <ListItemIcon><VisibilityIcon fontSize="small" /></ListItemIcon>
          <ListItemText>View detail</ListItemText>
        </MenuItem>
        <Tooltip title={editTooltip} placement="left">
          <span>
            <MenuItem onClick={() => { onEdit(); close(); }} disabled={editDisabled}>
              <ListItemIcon><EditIcon fontSize="small" color={editDisabled ? 'disabled' : 'inherit'} /></ListItemIcon>
              <ListItemText>Edit</ListItemText>
            </MenuItem>
          </span>
        </Tooltip>
        <Tooltip title={historyTooltip} placement="left">
          <span>
            <MenuItem onClick={() => { onHistory(); close(); }} disabled={historyDisabled}>
              <ListItemIcon><HistoryIcon fontSize="small" color={historyDisabled ? 'disabled' : 'inherit'} /></ListItemIcon>
              <ListItemText>View history</ListItemText>
            </MenuItem>
          </span>
        </Tooltip>
        <Divider />
        <Tooltip title={deleteTooltip} placement="left">
          <span>
            <MenuItem onClick={() => { onDelete(); close(); }} disabled={deleteDisabled} sx={{ color: deleteDisabled ? undefined : 'error.main' }}>
              <ListItemIcon><DeleteIcon fontSize="small" color={deleteDisabled ? 'disabled' : 'error'} /></ListItemIcon>
              <ListItemText>Delete</ListItemText>
            </MenuItem>
          </span>
        </Tooltip>
      </Menu>
    </>
  );
}

function Roles() {
  const navigate = useNavigate();
  const hasPermission = usePermissions();
  const canRead = hasPermission('roles:read');
  const { roles: builtinRoles, loading: builtinLoading, error: builtinError } = useBuiltinRolesList(canRead);
  const { roles, loading, error, refresh } = useRolesList(canRead);
  const { createRole, updateRole, deleteRole } = useRoleMutations();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<RoleItem | null>(null);
  const [detailTarget, setDetailTarget] = useState<RoleItem | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<RoleItem | null>(null);
  const [deleting, setDeleting] = useState(false);

  const allRows = useMemo(
    () => [...builtinRoles, ...roles],
    [builtinRoles, roles]
  );
  const availablePermissions = useMemo(
    () => Array.from(new Set([
      ...builtinRoles.flatMap((role) => role.permissions),
      ...(editTarget?.permissions ?? [])
    ])).sort(),
    [builtinRoles, editTarget]
  );

  const handleSave = async (req: CreateRoleRequest | UpdateRoleRequest) => {
    if (editTarget) {
      await updateRole(editTarget.role_id, req as UpdateRoleRequest);
    } else {
      await createRole(req as CreateRoleRequest);
    }
    refresh();
  };

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await deleteRole(deleteTarget.role_id);
      setDeleteTarget(null);
      refresh();
    } finally {
      setDeleting(false);
    }
  };

  if (!canRead) {
    return (
      <Box sx={{ p: 3 }}>
        <Typography>You do not have access to role management.</Typography>
      </Box>
    );
  }

  const isLoading = builtinLoading || loading;
  const loadError = builtinError || error;

  return (
    <>
      <Box sx={{ p: 3 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
          <Typography variant="h1">Roles</Typography>
          {hasPermission('roles:write') && (
            <Button
              variant="contained"
              startIcon={<AddIcon />}
              onClick={() => { setEditTarget(null); setDialogOpen(true); }}
            >
              New role
            </Button>
          )}
        </Box>

        {isLoading && (
          <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
            <CircularProgress />
          </Box>
        )}

        {loadError && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Error />
            <Typography>Failed to load roles</Typography>
          </Box>
        )}

        {!isLoading && !loadError && (
          <TableContainer component={Paper} variant="outlined">
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Name</TableCell>
                  <TableCell>Type</TableCell>
                  <TableCell>Description</TableCell>
                  <TableCell>Permissions</TableCell>
                  <TableCell>Version</TableCell>
                  <TableCell>Latest Update</TableCell>
                  <TableCell>Updated By</TableCell>
                  <TableCell />
                </TableRow>
              </TableHead>
              <TableBody>
                {allRows.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={8}>
                      <Typography color="text.secondary" sx={{ py: 1 }}>
                        No roles found.
                      </Typography>
                    </TableCell>
                  </TableRow>
                )}
                {allRows.map((item) => {
                  const builtin = isBuiltinRole(item.role_id);
                  const visiblePermissions = item.permissions.slice(0, 3);
                  const remaining = item.permissions.length - visiblePermissions.length;
                  return (
                    <TableRow key={item.role_id} hover>
                      <TableCell>
                        <Button
                          variant="text"
                          size="small"
                          onClick={() => setDetailTarget(item)}
                          sx={{ px: 0, minWidth: 0, textTransform: 'none', fontWeight: 700 }}
                        >
                          {item.name}
                        </Button>
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={builtin ? 'Built-in' : 'User-defined'}
                          size="small"
                          variant={builtin ? 'outlined' : 'filled'}
                          color={builtin ? 'primary' : 'default'}
                        />
                      </TableCell>
                      <TableCell sx={{ color: 'text.secondary', maxWidth: 320 }}>
                        <Typography variant="body2" color="text.secondary" sx={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {item.description || '-'}
                        </Typography>
                      </TableCell>
                      <TableCell sx={{ minWidth: 250 }}>
                        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                          {visiblePermissions.map((permission) => (
                            <Chip key={permission} label={permission} size="small" variant="outlined" />
                          ))}
                          {remaining > 0 && (
                            <Chip label={`+${remaining}`} size="small" variant="outlined" />
                          )}
                        </Box>
                      </TableCell>
                      <TableCell sx={{ color: 'text.secondary' }}>
                        {builtin ? '-' : `v${item.current_version}`}
                      </TableCell>
                      <TableCell sx={{ color: 'text.secondary' }}>
                        {builtin || !item.updated_at ? '-' : new Date(item.updated_at).toLocaleString()}
                      </TableCell>
                      <TableCell sx={{ color: 'text.secondary' }}>
                        {builtin ? '-' : (
                          item.updated_by
                            ? <UserDisplay userId={item.updated_by} />
                            : <UserDisplay userId={item.created_by} />
                        )}
                      </TableCell>
                      <TableCell align="right" sx={{ width: 48, pr: 1 }}>
                        <RowMenu
                          isBuiltin={builtin}
                          onView={() => setDetailTarget(item)}
                          onEdit={() => { setEditTarget(item); setDialogOpen(true); }}
                          onHistory={() => navigate(`/app/roles/${item.role_id}/history`)}
                          onDelete={() => setDeleteTarget(item)}
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

      <RoleDialog
        key={editTarget?.role_id ?? 'new'}
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        onSave={handleSave}
        initial={editTarget}
        availablePermissions={availablePermissions}
      />

      <RoleDetailDialog role={detailTarget} onClose={() => setDetailTarget(null)} />

      <Dialog open={!!deleteTarget} onClose={() => setDeleteTarget(null)} maxWidth="xs" fullWidth>
        <DialogTitle>Delete role?</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Permanently delete <strong>{deleteTarget?.name}</strong> and all its versions?
            This cannot be undone.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteTarget(null)} disabled={deleting}>
            Cancel
          </Button>
          <Button variant="contained" color="error" onClick={handleDeleteConfirm} disabled={deleting}>
            {deleting ? <CircularProgress size={20} /> : 'Delete'}
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}

export default Roles;
