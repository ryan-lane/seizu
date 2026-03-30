import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
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
  FormControl,
  FormControlLabel,
  IconButton,
  InputLabel,
  ListItemIcon,
  ListItemText,
  Menu,
  MenuItem,
  Paper,
  Select,
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
import AddCircleOutlineIcon from '@mui/icons-material/AddCircleOutline';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import DeleteIcon from '@mui/icons-material/Delete';
import EditIcon from '@mui/icons-material/Edit';
import HistoryIcon from '@mui/icons-material/History';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import RemoveCircleOutlineIcon from '@mui/icons-material/RemoveCircleOutline';
import Error from '@mui/icons-material/Error';
import {
  useToolsList,
  useToolMutations,
  ToolItem,
  ToolParamDef,
  CreateToolRequest,
  UpdateToolRequest
} from 'src/hooks/useToolsetsApi';
import ToolDetailDialog, { ToolViewData } from 'src/components/ToolDetailDialog';
import UserDisplay from 'src/components/UserDisplay';
import { usePermissions } from 'src/hooks/usePermissions';

// ---------------------------------------------------------------------------
// Built-in seizu toolset sentinel
// ---------------------------------------------------------------------------

const BUILTIN_TOOLSET_ID = '__builtin_seizu__';

const BUILTIN_TOOLS: ToolItem[] = [
  {
    tool_id: '__builtin_seizu__schema__',
    toolset_id: BUILTIN_TOOLSET_ID,
    name: 'schema',
    description:
      'Returns the available node labels, relationship types, and property keys in the Neo4j graph database.',
    cypher: '-- Built-in: CALL db.labels(), CALL db.relationshipTypes(), CALL db.propertyKeys()',
    parameters: [],
    enabled: true,
    current_version: 1,
    created_at: '',
    updated_at: '',
    created_by: '',
    updated_by: null
  },
  {
    tool_id: '__builtin_seizu__query__',
    toolset_id: BUILTIN_TOOLSET_ID,
    name: 'query',
    description:
      'Execute an ad-hoc read-only Cypher query against the Neo4j graph database. The query is validated before execution — write operations are not permitted.',
    cypher: '-- Built-in: executes the provided query parameter after validation',
    parameters: [
      {
        name: 'query',
        type: 'string',
        description: 'A read-only Cypher query to execute.',
        required: true,
        default: null
      }
    ],
    enabled: true,
    current_version: 1,
    created_at: '',
    updated_at: '',
    created_by: '',
    updated_by: null
  }
];

// ---------------------------------------------------------------------------
// Param form state
// ---------------------------------------------------------------------------

type ParamFormState = {
  name: string;
  type: ToolParamDef['type'];
  description: string;
  required: boolean;
  default_str: string;
};

const EMPTY_PARAM: ParamFormState = {
  name: '',
  type: 'string',
  description: '',
  required: true,
  default_str: ''
};

function paramToFormState(p: ToolParamDef): ParamFormState {
  return {
    name: p.name,
    type: p.type,
    description: p.description ?? '',
    required: p.required,
    default_str: p.default !== null && p.default !== undefined ? String(p.default) : ''
  };
}

function formStateToParam(p: ParamFormState): ToolParamDef {
  let defaultVal: unknown = null;
  if (p.default_str.trim() !== '') {
    if (p.type === 'integer') {
      defaultVal = parseInt(p.default_str, 10);
    } else if (p.type === 'float') {
      defaultVal = parseFloat(p.default_str);
    } else if (p.type === 'boolean') {
      defaultVal = p.default_str.toLowerCase() === 'true';
    } else {
      defaultVal = p.default_str;
    }
  }
  return {
    name: p.name,
    type: p.type,
    description: p.description,
    required: p.required,
    default: defaultVal
  };
}

// ---------------------------------------------------------------------------
// Create/Edit dialog
// ---------------------------------------------------------------------------

interface ToolDialogProps {
  open: boolean;
  onClose: () => void;
  onSave: (req: CreateToolRequest | UpdateToolRequest) => Promise<void>;
  initial: ToolItem | null;
}

function ToolDialog({ open, onClose, onSave, initial }: ToolDialogProps) {
  const [name, setName] = useState(initial?.name ?? '');
  const [description, setDescription] = useState(initial?.description ?? '');
  const [cypher, setCypher] = useState(initial?.cypher ?? '');
  const [enabled, setEnabled] = useState(initial?.enabled ?? true);
  const [params, setParams] = useState<ParamFormState[]>(
    (initial?.parameters ?? []).map(paramToFormState)
  );
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
    if (!cypher.trim()) {
      setError('Cypher query is required.');
      return;
    }
    for (const p of params) {
      if (!p.name.trim()) {
        setError('All parameters must have a name.');
        return;
      }
    }
    const req: CreateToolRequest | UpdateToolRequest = {
      name: name.trim(),
      description: description.trim(),
      cypher: cypher.trim(),
      parameters: params.map(formStateToParam),
      enabled,
      ...(initial ? { comment: comment.trim() || null } : {})
    };
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

  const addParam = () => setParams((ps) => [...ps, { ...EMPTY_PARAM }]);
  const removeParam = (i: number) => setParams((ps) => ps.filter((_, idx) => idx !== i));
  const updateParam = <K extends keyof ParamFormState>(i: number, key: K, val: ParamFormState[K]) =>
    setParams((ps) => ps.map((p, idx) => (idx === i ? { ...p, [key]: val } : p)));

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="md" fullWidth>
      <DialogTitle>{initial ? 'Edit Tool' : 'New Tool'}</DialogTitle>
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
          <TextField
            label="Cypher Query"
            value={cypher}
            onChange={(e) => setCypher(e.target.value)}
            fullWidth
            required
            multiline
            minRows={5}
            inputProps={{ style: { fontFamily: 'monospace', fontSize: 13 } }}
          />
          <FormControlLabel
            control={<Switch checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />}
            label="Enabled"
          />

          <Divider />

          <Box>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
              <Typography variant="subtitle2">Parameters</Typography>
              <IconButton size="small" onClick={addParam}>
                <AddCircleOutlineIcon fontSize="small" />
              </IconButton>
            </Box>
            {params.length === 0 && (
              <Typography variant="body2" color="text.secondary">
                No parameters. Click + to add one.
              </Typography>
            )}
            {params.map((p, i) => (
              <Box
                key={i}
                sx={{
                  border: '1px solid',
                  borderColor: 'divider',
                  borderRadius: 1,
                  p: 1.5,
                  mb: 1.5,
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 1
                }}
              >
                <Box sx={{ display: 'flex', gap: 1, alignItems: 'flex-start' }}>
                  <TextField
                    label="Name"
                    value={p.name}
                    onChange={(e) => updateParam(i, 'name', e.target.value)}
                    size="small"
                    sx={{ flex: 2 }}
                    required
                  />
                  <FormControl size="small" sx={{ flex: 1 }}>
                    <InputLabel>Type</InputLabel>
                    <Select
                      label="Type"
                      value={p.type}
                      onChange={(e) => updateParam(i, 'type', e.target.value as ToolParamDef['type'])}
                    >
                      <MenuItem value="string">string</MenuItem>
                      <MenuItem value="integer">integer</MenuItem>
                      <MenuItem value="float">float</MenuItem>
                      <MenuItem value="boolean">boolean</MenuItem>
                    </Select>
                  </FormControl>
                  <TextField
                    label="Default"
                    value={p.default_str}
                    onChange={(e) => updateParam(i, 'default_str', e.target.value)}
                    size="small"
                    sx={{ flex: 1 }}
                    placeholder="optional"
                  />
                  <FormControlLabel
                    control={
                      <Checkbox
                        checked={p.required}
                        onChange={(e) => updateParam(i, 'required', e.target.checked)}
                        size="small"
                      />
                    }
                    label="Required"
                    sx={{ flexShrink: 0 }}
                  />
                  <IconButton size="small" onClick={() => removeParam(i)} sx={{ mt: 0.5, flexShrink: 0 }}>
                    <RemoveCircleOutlineIcon fontSize="small" />
                  </IconButton>
                </Box>
                <TextField
                  label="Description"
                  value={p.description}
                  onChange={(e) => updateParam(i, 'description', e.target.value)}
                  size="small"
                  fullWidth
                />
              </Box>
            ))}
          </Box>

          {initial && (
            <>
              <Divider />
              <TextField
                label="Comment (optional)"
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                fullWidth
                size="small"
                placeholder="Describe what changed…"
              />
            </>
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
  item: ToolItem;
  isBuiltin: boolean;
  onEdit: () => void;
  onDetail: () => void;
  onHistory: () => void;
  onDelete: () => void;
}

function RowMenu({ isBuiltin, onEdit, onDetail, onHistory, onDelete }: RowMenuProps) {
  const [anchor, setAnchor] = useState<null | HTMLElement>(null);
  const hasPermission = usePermissions();
  const close = () => setAnchor(null);

  const canWrite = hasPermission('tools:write');
  const canDelete = hasPermission('tools:delete');

  const editDisabled = isBuiltin || !canWrite;
  const deleteDisabled = isBuiltin || !canDelete;
  const editTooltip = isBuiltin ? 'Built-in tools cannot be edited' : !canWrite ? 'You do not have permission to edit tools' : '';
  const deleteTooltip = isBuiltin ? 'Built-in tools cannot be deleted' : !canDelete ? 'You do not have permission to delete tools' : '';

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
        <MenuItem onClick={() => { onDetail(); close(); }}>
          <ListItemIcon><HistoryIcon fontSize="small" /></ListItemIcon>
          <ListItemText>View detail</ListItemText>
        </MenuItem>

        <Tooltip title={editTooltip} placement="left">
          <span>
            <MenuItem onClick={() => { onEdit(); close(); }} disabled={editDisabled}>
              <ListItemIcon><EditIcon fontSize="small" /></ListItemIcon>
              <ListItemText>Edit</ListItemText>
            </MenuItem>
          </span>
        </Tooltip>

        <Tooltip title={isBuiltin ? 'Built-in tools have no version history' : ''} placement="left">
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

function ToolsetTools() {
  const { toolsetId } = useParams();
  const navigate = useNavigate();
  const hasPermission = usePermissions();

  const isBuiltin = toolsetId === BUILTIN_TOOLSET_ID;
  const { tools, loading, error, refresh } = useToolsList(isBuiltin ? null : (toolsetId ?? null));
  const mutations = useToolMutations(toolsetId ?? '');

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<ToolItem | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<ToolItem | null>(null);
  const [detailItem, setDetailItem] = useState<ToolViewData | null>(null);
  const [deleting, setDeleting] = useState(false);

  const openCreate = () => {
    setEditTarget(null);
    setDialogOpen(true);
  };

  const openEdit = (item: ToolItem) => {
    setEditTarget(item);
    setDialogOpen(true);
  };

  const handleSave = async (req: CreateToolRequest | UpdateToolRequest) => {
    if (editTarget) {
      await mutations.updateTool(editTarget.tool_id, req as UpdateToolRequest);
    } else {
      await mutations.createTool(req as CreateToolRequest);
    }
    refresh();
  };

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await mutations.deleteTool(deleteTarget.tool_id);
      setDeleteTarget(null);
      refresh();
    } catch {
      // dialog stays open so user can retry
    } finally {
      setDeleting(false);
    }
  };

  const displayTools: ToolItem[] = isBuiltin ? BUILTIN_TOOLS : tools;

  return (
    <>
      <Box sx={{ p: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
          <Button
            size="small"
            startIcon={<ArrowBackIcon />}
            onClick={() => navigate('/app/toolsets')}
          >
            Back to toolsets
          </Button>
        </Box>

        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
          <Typography variant="h1">
            Tools
            {isBuiltin && (
              <Chip label="Built-in" size="small" variant="outlined" color="primary" sx={{ ml: 1, verticalAlign: 'middle' }} />
            )}
          </Typography>
          {!isBuiltin && hasPermission('tools:write') && (
            <Button variant="contained" startIcon={<AddIcon />} onClick={openCreate}>
              New tool
            </Button>
          )}
        </Box>

        {!isBuiltin && loading && <CircularProgress />}

        {!isBuiltin && error && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Error />
            <Typography>Failed to load tools</Typography>
          </Box>
        )}

        {(isBuiltin || (!loading && !error)) && (
          <TableContainer component={Paper} variant="outlined">
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Name</TableCell>
                  <TableCell>Description</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Parameters</TableCell>
                  <TableCell>Version</TableCell>
                  <TableCell>Latest Update</TableCell>
                  <TableCell>Updated By</TableCell>
                  <TableCell />
                </TableRow>
              </TableHead>
              <TableBody>
                {displayTools.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={8}>
                      <Typography color="text.secondary" sx={{ py: 1 }}>
                        No tools yet. Create one above.
                      </Typography>
                    </TableCell>
                  </TableRow>
                )}
                {displayTools.map((item) => {
                  const itemIsBuiltin = item.toolset_id === BUILTIN_TOOLSET_ID;
                  return (
                    <TableRow key={item.tool_id} hover>
                      <TableCell>
                        <Typography
                          variant="body2"
                          fontWeight={500}
                          sx={{ cursor: 'pointer', '&:hover': { textDecoration: 'underline' } }}
                          onClick={() =>
                            setDetailItem({
                              name: item.name,
                              description: item.description,
                              cypher: item.cypher,
                              parameters: item.parameters,
                              enabled: item.enabled
                            })
                          }
                        >
                          {item.name}
                        </Typography>
                      </TableCell>
                      <TableCell sx={{ color: 'text.secondary', maxWidth: 280 }}>
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
                        {item.parameters.length === 0 ? '—' : item.parameters.length}
                      </TableCell>
                      <TableCell sx={{ color: 'text.secondary' }}>
                        {itemIsBuiltin ? '—' : `v${item.current_version}`}
                      </TableCell>
                      <TableCell sx={{ color: 'text.secondary' }}>
                        {itemIsBuiltin || !item.updated_at ? '—' : new Date(item.updated_at).toLocaleString()}
                      </TableCell>
                      <TableCell sx={{ color: 'text.secondary' }}>
                        {itemIsBuiltin ? '—' : (
                          item.updated_by
                            ? <UserDisplay userId={item.updated_by} />
                            : <UserDisplay userId={item.created_by} />
                        )}
                      </TableCell>
                      <TableCell align="right" sx={{ width: 48, pr: 1 }}>
                        <RowMenu
                          item={item}
                          isBuiltin={itemIsBuiltin}
                          onEdit={() => openEdit(item)}
                          onDetail={() =>
                            setDetailItem({
                              name: item.name,
                              description: item.description,
                              cypher: item.cypher,
                              parameters: item.parameters,
                              enabled: item.enabled
                            })
                          }
                          onHistory={() =>
                            navigate(`/app/toolsets/${toolsetId}/tools/${item.tool_id}/history`)
                          }
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

      {!isBuiltin && (
        <ToolDialog
          key={editTarget?.tool_id ?? 'new'}
          open={dialogOpen}
          onClose={() => setDialogOpen(false)}
          onSave={handleSave}
          initial={editTarget}
        />
      )}

      <ToolDetailDialog
        open={!!detailItem}
        onClose={() => setDetailItem(null)}
        data={detailItem}
      />

      {/* Delete confirmation dialog */}
      <Dialog open={!!deleteTarget} onClose={() => setDeleteTarget(null)} maxWidth="xs" fullWidth>
        <DialogTitle>Delete tool?</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Permanently delete <strong>{deleteTarget?.name}</strong> and all its versions? This
            cannot be undone.
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

export default ToolsetTools;
