import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Alert,
  Box,
  Button,
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
  Switch,
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
import BuildIcon from '@mui/icons-material/Build';
import DeleteIcon from '@mui/icons-material/Delete';
import EditIcon from '@mui/icons-material/Edit';
import HistoryIcon from '@mui/icons-material/History';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import Error from '@mui/icons-material/Error';
import {
  useToolsetsList,
  useToolsetMutations,
  ToolsetListItem,
  CreateToolsetRequest,
  UpdateToolsetRequest
} from 'src/hooks/useToolsetsApi';
import UserDisplay from 'src/components/UserDisplay';
import { usePermissions } from 'src/hooks/usePermissions';

// ---------------------------------------------------------------------------
// Built-in synthetic toolsets
// ---------------------------------------------------------------------------
// The backend surfaces built-in groups through the same /api/v1/toolsets
// endpoint with ids prefixed by `__builtin_`.  We only need the prefix here
// to hide edit/delete actions on those rows.

const BUILTIN_PREFIX = '__builtin_';

const isBuiltinToolset = (id: string): boolean =>
  id.startsWith(BUILTIN_PREFIX) && id.endsWith('__');

const LOWER_SNAKE_ID = /^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$/;

// ---------------------------------------------------------------------------
// Create/Edit dialog
// ---------------------------------------------------------------------------

interface ToolsetDialogProps {
  open: boolean;
  onClose: () => void;
  onSave: (req: CreateToolsetRequest | UpdateToolsetRequest) => Promise<void>;
  initial: ToolsetListItem | null;
}

function ToolsetDialog({ open, onClose, onSave, initial }: ToolsetDialogProps) {
  const [toolsetId, setToolsetId] = useState(initial?.toolset_id ?? '');
  const [name, setName] = useState(initial?.name ?? '');
  const [description, setDescription] = useState(initial?.description ?? '');
  const [enabled, setEnabled] = useState(initial?.enabled ?? true);
  const [comment, setComment] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleClose = () => {
    setError(null);
    onClose();
  };

  const handleSave = async () => {
    setError(null);
    if (!name.trim()) {
      setError('Name is required.');
      return;
    }
    if (!initial && !LOWER_SNAKE_ID.test(toolsetId.trim())) {
      setError('ID must be lower_snake_case.');
      return;
    }
    const req = initial
      ? ({ name: name.trim(), description: description.trim(), enabled, comment: comment.trim() || null } as UpdateToolsetRequest)
      : ({ toolset_id: toolsetId.trim(), name: name.trim(), description: description.trim(), enabled } as CreateToolsetRequest);
    setSaving(true);
    try {
      await onSave(req);
      handleClose();
    } catch (err) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      setError((err as any)?.message ?? 'Failed to save.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <DialogTitle>{initial ? 'Edit Toolset' : 'New Toolset'}</DialogTitle>
      <DialogContent dividers>
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {!initial && (
            <TextField
              label="ID"
              value={toolsetId}
              onChange={(e) => setToolsetId(e.target.value)}
              fullWidth
              required
              helperText="lower_snake_case"
            />
          )}
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
          <FormControlLabel
            control={<Switch checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />}
            label="Enabled"
          />
          {initial && (
            <TextField
              label="Comment (optional)"
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              fullWidth
              size="small"
              placeholder="Describe what changed…"
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

// ---------------------------------------------------------------------------
// Per-row overflow menu
// ---------------------------------------------------------------------------

interface RowMenuProps {
  item: ToolsetListItem;
  isBuiltin: boolean;
  onEdit: () => void;
  onTools: () => void;
  onHistory: () => void;
  onDelete: () => void;
}

function RowMenu({ isBuiltin, onEdit, onTools, onHistory, onDelete }: RowMenuProps) {
  const [anchor, setAnchor] = useState<null | HTMLElement>(null);
  const hasPermission = usePermissions();
  const close = () => setAnchor(null);

  const canWrite = hasPermission('toolsets:write');
  const canDelete = hasPermission('toolsets:delete');

  const editDisabled = isBuiltin || !canWrite;
  const deleteDisabled = isBuiltin || !canDelete;
  const editTooltip = isBuiltin ? 'Built-in toolsets cannot be edited' : !canWrite ? 'You do not have permission to edit toolsets' : '';
  const deleteTooltip = isBuiltin ? 'Built-in toolsets cannot be deleted' : !canDelete ? 'You do not have permission to delete toolsets' : '';

  return (
    <>
      <Tooltip title="More actions">
        <IconButton size="small" onClick={(e) => setAnchor(e.currentTarget)}>
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
        <Tooltip title={editTooltip} placement="left">
          <span>
            <MenuItem onClick={() => { onEdit(); close(); }} disabled={editDisabled}>
              <ListItemIcon><EditIcon fontSize="small" /></ListItemIcon>
              <ListItemText>Edit</ListItemText>
            </MenuItem>
          </span>
        </Tooltip>

        <MenuItem onClick={() => { onTools(); close(); }}>
          <ListItemIcon><BuildIcon fontSize="small" /></ListItemIcon>
          <ListItemText>View tools</ListItemText>
        </MenuItem>

        <Tooltip title={isBuiltin ? 'Built-in toolsets have no version history' : ''} placement="left">
          <span>
            <MenuItem onClick={() => { onHistory(); close(); }} disabled={isBuiltin}>
              <ListItemIcon><HistoryIcon fontSize="small" /></ListItemIcon>
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

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

function Toolsets() {
  const navigate = useNavigate();
  const { toolsets, loading, error, refresh } = useToolsetsList();
  const { createToolset, updateToolset, deleteToolset } = useToolsetMutations();
  const hasPermission = usePermissions();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<ToolsetListItem | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<ToolsetListItem | null>(null);
  const [deleting, setDeleting] = useState(false);

  const openCreate = () => {
    setEditTarget(null);
    setDialogOpen(true);
  };

  const openEdit = (item: ToolsetListItem) => {
    setEditTarget(item);
    setDialogOpen(true);
  };

  const handleSave = async (req: CreateToolsetRequest | UpdateToolsetRequest) => {
    if (editTarget) {
      await updateToolset(editTarget.toolset_id, req as UpdateToolsetRequest);
    } else {
      await createToolset(req as CreateToolsetRequest);
    }
    refresh();
  };

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await deleteToolset(deleteTarget.toolset_id);
      setDeleteTarget(null);
      refresh();
    } catch {
      // dialog stays open so user can retry
    } finally {
      setDeleting(false);
    }
  };

  const allRows: ToolsetListItem[] = toolsets;

  return (
    <>
      <Box sx={{ p: 3 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
          <Typography variant="h1">MCP Toolsets</Typography>
          {hasPermission('toolsets:write') && (
            <Button variant="contained" startIcon={<AddIcon />} onClick={openCreate}>
              New toolset
            </Button>
          )}
        </Box>

        {loading && (
          <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
            <CircularProgress />
          </Box>
        )}

        {error && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Error />
            <Typography>Failed to load toolsets</Typography>
          </Box>
        )}

        {!loading && !error && (
          <TableContainer component={Paper} variant="outlined">
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Name</TableCell>
                  <TableCell>Slug</TableCell>
                  <TableCell>Description</TableCell>
                  <TableCell>Status</TableCell>
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
                        No toolsets yet. Create one above.
                      </Typography>
                    </TableCell>
                  </TableRow>
                )}
                {allRows.map((item) => {
                  const isBuiltin = isBuiltinToolset(item.toolset_id);
                  return (
                    <TableRow key={item.toolset_id} hover>
                      <TableCell>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <Typography
                            variant="body2"
                            fontWeight={500}
                            sx={{ cursor: 'pointer', '&:hover': { textDecoration: 'underline' } }}
                            onClick={() => navigate(`/app/toolsets/${item.toolset_id}/tools`)}
                          >
                            {item.name}
                          </Typography>
                          {isBuiltin && (
                            <Chip label="Built-in" size="small" variant="outlined" color="primary" />
                          )}
                        </Box>
                      </TableCell>
                      <TableCell sx={{ color: 'text.secondary', fontFamily: 'monospace' }}>
                        {item.toolset_id}
                      </TableCell>
                      <TableCell sx={{ color: 'text.secondary', maxWidth: 320 }}>
                        <Typography
                          variant="body2"
                          color="text.secondary"
                          sx={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                        >
                          {item.description || '—'}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={item.enabled ? 'Enabled' : 'Disabled'}
                          color={item.enabled ? 'success' : 'default'}
                          size="small"
                        />
                      </TableCell>
                      <TableCell sx={{ color: 'text.secondary' }}>
                        {isBuiltin ? '—' : `v${item.current_version}`}
                      </TableCell>
                      <TableCell sx={{ color: 'text.secondary' }}>
                        {isBuiltin || !item.updated_at ? '—' : new Date(item.updated_at).toLocaleString()}
                      </TableCell>
                      <TableCell sx={{ color: 'text.secondary' }}>
                        {isBuiltin ? '—' : (
                          item.updated_by
                            ? <UserDisplay userId={item.updated_by} />
                            : <UserDisplay userId={item.created_by} />
                        )}
                      </TableCell>
                      <TableCell align="right" sx={{ width: 48, pr: 1 }}>
                        <RowMenu
                          item={item}
                          isBuiltin={isBuiltin}
                          onEdit={() => openEdit(item)}
                          onTools={() => navigate(`/app/toolsets/${item.toolset_id}/tools`)}
                          onHistory={() => navigate(`/app/toolsets/${item.toolset_id}/history`)}
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

      <ToolsetDialog
        key={editTarget?.toolset_id ?? 'new'}
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        onSave={handleSave}
        initial={editTarget}
      />

      {/* Delete confirmation dialog */}
      <Dialog open={!!deleteTarget} onClose={() => setDeleteTarget(null)} maxWidth="xs" fullWidth>
        <DialogTitle>Delete toolset?</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Permanently delete <strong>{deleteTarget?.name}</strong> and all its tools and versions?
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

export default Toolsets;
