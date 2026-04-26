import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Alert, Box, Button, Chip, CircularProgress, Dialog, DialogActions, DialogContent,
  DialogContentText, DialogTitle, Divider, FormControlLabel, IconButton, ListItemIcon,
  ListItemText, Menu, MenuItem, Paper, Switch, Table, TableBody, TableCell,
  TableContainer, TableHead, TableRow, TextField, Tooltip, Typography
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import PsychologyIcon from '@mui/icons-material/Psychology';
import DeleteIcon from '@mui/icons-material/Delete';
import EditIcon from '@mui/icons-material/Edit';
import HistoryIcon from '@mui/icons-material/History';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import Error from '@mui/icons-material/Error';
import {
  useSkillsetsList, useSkillsetMutations, SkillsetListItem,
  CreateSkillsetRequest, UpdateSkillsetRequest
} from 'src/hooks/useSkillsetsApi';
import UserDisplay from 'src/components/UserDisplay';
import { usePermissions } from 'src/hooks/usePermissions';

const LOWER_SNAKE_ID = /^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$/;

interface SkillsetDialogProps {
  open: boolean;
  onClose: () => void;
  onSave: (req: CreateSkillsetRequest | UpdateSkillsetRequest) => Promise<void>;
  initial: SkillsetListItem | null;
}

function SkillsetDialog({ open, onClose, onSave, initial }: SkillsetDialogProps) {
  const [skillsetId, setSkillsetId] = useState(initial?.skillset_id ?? '');
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
    if (!initial && !LOWER_SNAKE_ID.test(skillsetId.trim())) {
      setError('ID must be lower_snake_case.');
      return;
    }
    const req = initial
      ? ({ name: name.trim(), description: description.trim(), enabled, comment: comment.trim() || null } as UpdateSkillsetRequest)
      : ({ skillset_id: skillsetId.trim(), name: name.trim(), description: description.trim(), enabled } as CreateSkillsetRequest);
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
      <DialogTitle>{initial ? 'Edit Skillset' : 'New Skillset'}</DialogTitle>
      <DialogContent dividers>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {!initial && (
            <TextField label="ID" value={skillsetId} onChange={(e) => setSkillsetId(e.target.value)} fullWidth required helperText="lower_snake_case" />
          )}
          <TextField label="Name" value={name} onChange={(e) => setName(e.target.value)} fullWidth required />
          <TextField label="Description" value={description} onChange={(e) => setDescription(e.target.value)} fullWidth multiline minRows={2} />
          <FormControlLabel control={<Switch checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />} label="Enabled" />
          {initial && (
            <TextField label="Comment (optional)" value={comment} onChange={(e) => setComment(e.target.value)} fullWidth size="small" placeholder="Describe what changed..." />
          )}
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose} disabled={saving}>Cancel</Button>
        <Button onClick={handleSave} variant="contained" disabled={saving}>
          {saving ? <CircularProgress size={20} /> : 'Save'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

interface RowMenuProps {
  item: SkillsetListItem;
  onEdit: () => void;
  onSkills: () => void;
  onHistory: () => void;
  onDelete: () => void;
}

function RowMenu({ onEdit, onSkills, onHistory, onDelete }: RowMenuProps) {
  const [anchor, setAnchor] = useState<null | HTMLElement>(null);
  const hasPermission = usePermissions();
  const close = () => setAnchor(null);
  const canWrite = hasPermission('skillsets:write');
  const canDelete = hasPermission('skillsets:delete');

  return (
    <>
      <Tooltip title="More actions">
        <IconButton size="small" onClick={(e) => setAnchor(e.currentTarget)}>
          <MoreVertIcon fontSize="small" />
        </IconButton>
      </Tooltip>
      <Menu anchorEl={anchor} open={!!anchor} onClose={close} anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }} transformOrigin={{ vertical: 'top', horizontal: 'right' }} slotProps={{ paper: { sx: { minWidth: 180 } } }}>
        <Tooltip title={canWrite ? '' : 'You do not have permission to edit skillsets'} placement="left">
          <span>
            <MenuItem onClick={() => { onEdit(); close(); }} disabled={!canWrite}>
              <ListItemIcon><EditIcon fontSize="small" /></ListItemIcon>
              <ListItemText>Edit</ListItemText>
            </MenuItem>
          </span>
        </Tooltip>
        <MenuItem onClick={() => { onSkills(); close(); }}>
          <ListItemIcon><PsychologyIcon fontSize="small" /></ListItemIcon>
          <ListItemText>View skills</ListItemText>
        </MenuItem>
        <MenuItem onClick={() => { onHistory(); close(); }}>
          <ListItemIcon><HistoryIcon fontSize="small" /></ListItemIcon>
          <ListItemText>View history</ListItemText>
        </MenuItem>
        <Divider />
        <Tooltip title={canDelete ? '' : 'You do not have permission to delete skillsets'} placement="left">
          <span>
            <MenuItem onClick={() => { onDelete(); close(); }} disabled={!canDelete} sx={{ color: canDelete ? 'error.main' : undefined }}>
              <ListItemIcon><DeleteIcon fontSize="small" color={canDelete ? 'error' : 'disabled'} /></ListItemIcon>
              <ListItemText>Delete</ListItemText>
            </MenuItem>
          </span>
        </Tooltip>
      </Menu>
    </>
  );
}

function Skillsets() {
  const navigate = useNavigate();
  const { skillsets, loading, error, refresh } = useSkillsetsList();
  const { createSkillset, updateSkillset, deleteSkillset } = useSkillsetMutations();
  const hasPermission = usePermissions();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<SkillsetListItem | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<SkillsetListItem | null>(null);
  const [deleting, setDeleting] = useState(false);

  const handleSave = async (req: CreateSkillsetRequest | UpdateSkillsetRequest) => {
    if (editTarget) await updateSkillset(editTarget.skillset_id, req as UpdateSkillsetRequest);
    else await createSkillset(req as CreateSkillsetRequest);
    refresh();
  };

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await deleteSkillset(deleteTarget.skillset_id);
      setDeleteTarget(null);
      refresh();
    } finally {
      setDeleting(false);
    }
  };

  return (
    <>
      <Box sx={{ p: 3 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
          <Typography variant="h1">MCP Skillsets</Typography>
          {hasPermission('skillsets:write') && (
            <Button variant="contained" startIcon={<AddIcon />} onClick={() => { setEditTarget(null); setDialogOpen(true); }}>New skillset</Button>
          )}
        </Box>
        {loading && <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}><CircularProgress /></Box>}
        {error && <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}><Error /><Typography>Failed to load skillsets</Typography></Box>}
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
                {skillsets.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={8}><Typography color="text.secondary" sx={{ py: 1 }}>No skillsets yet. Create one above.</Typography></TableCell>
                  </TableRow>
                )}
                {skillsets.map((item) => (
                  <TableRow key={item.skillset_id} hover>
                    <TableCell>
                      <Typography variant="body2" fontWeight={500} sx={{ cursor: 'pointer', '&:hover': { textDecoration: 'underline' } }} onClick={() => navigate(`/app/skillsets/${item.skillset_id}/skills`)}>
                        {item.name}
                      </Typography>
                    </TableCell>
                    <TableCell sx={{ color: 'text.secondary', fontFamily: 'monospace' }}>{item.skillset_id}</TableCell>
                    <TableCell sx={{ color: 'text.secondary', maxWidth: 320 }}>
                      <Typography variant="body2" color="text.secondary" sx={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{item.description || '-'}</Typography>
                    </TableCell>
                    <TableCell><Chip label={item.enabled ? 'Enabled' : 'Disabled'} color={item.enabled ? 'success' : 'default'} size="small" /></TableCell>
                    <TableCell sx={{ color: 'text.secondary' }}>{`v${item.current_version}`}</TableCell>
                    <TableCell sx={{ color: 'text.secondary' }}>{item.updated_at ? new Date(item.updated_at).toLocaleString() : '-'}</TableCell>
                    <TableCell sx={{ color: 'text.secondary' }}>{item.updated_by ? <UserDisplay userId={item.updated_by} /> : <UserDisplay userId={item.created_by} />}</TableCell>
                    <TableCell align="right" sx={{ width: 48, pr: 1 }}>
                      <RowMenu
                        item={item}
                        onEdit={() => { setEditTarget(item); setDialogOpen(true); }}
                        onSkills={() => navigate(`/app/skillsets/${item.skillset_id}/skills`)}
                        onHistory={() => navigate(`/app/skillsets/${item.skillset_id}/history`)}
                        onDelete={() => setDeleteTarget(item)}
                      />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Box>
      <SkillsetDialog key={editTarget?.skillset_id ?? 'new'} open={dialogOpen} onClose={() => setDialogOpen(false)} onSave={handleSave} initial={editTarget} />
      <Dialog open={!!deleteTarget} onClose={() => setDeleteTarget(null)} maxWidth="xs" fullWidth>
        <DialogTitle>Delete skillset?</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Permanently delete <strong>{deleteTarget?.name}</strong> and all its skills and versions?
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteTarget(null)} disabled={deleting}>Cancel</Button>
          <Button variant="contained" color="error" onClick={handleDeleteConfirm} disabled={deleting}>{deleting ? <CircularProgress size={20} /> : 'Delete'}</Button>
        </DialogActions>
      </Dialog>
    </>
  );
}

export default Skillsets;
