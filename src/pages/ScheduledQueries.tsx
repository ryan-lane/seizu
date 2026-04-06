import { useState, useContext } from 'react';
import { useNavigate } from 'react-router-dom';
import {
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
  FormLabel,
  IconButton,
  InputLabel,
  ListItemIcon,
  ListItemText,
  Menu,
  MenuItem,
  Paper,
  Radio,
  RadioGroup,
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
  Typography,
  Alert
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import EditIcon from '@mui/icons-material/Edit';
import FiberManualRecordIcon from '@mui/icons-material/FiberManualRecord';
import HistoryIcon from '@mui/icons-material/History';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import AddCircleOutlineIcon from '@mui/icons-material/AddCircleOutline';
import RemoveCircleOutlineIcon from '@mui/icons-material/RemoveCircleOutline';
import Error from '@mui/icons-material/Error';
import {
  useScheduledQueriesList,
  useScheduledQueriesMutations,
  ScheduledQueryItem,
  ScheduledQueryRequest,
  ScheduledQueryParam,
  ScheduledQueryWatchScan,
  ScheduledQueryAction
} from 'src/hooks/useScheduledQueriesApi';
import { ConfigContext, ActionConfigFieldDef } from 'src/config.context';
import ScheduledQueryDetailDialog, {
  ScheduledQueryViewData
} from 'src/components/ScheduledQueryDetailDialog';
import UserDisplay from 'src/components/UserDisplay';
import { usePermissions } from 'src/hooks/usePermissions';

const EMPTY_FORM: ScheduledQueryRequest = {
  name: '',
  cypher: '',
  params: [],
  frequency: 60,
  watch_scans: [],
  enabled: true,
  actions: [],
  comment: null
};

type TriggerType = 'frequency' | 'watch_scans';

type ParamValueType = 'string' | 'list';

type ParamFormState = {
  name: string;
  value_str: string;
  value_type: ParamValueType;
};

type ActionFormState = {
  action_type: string;
  action_config: Record<string, unknown>;
};

function paramToFormState(p: ScheduledQueryParam): ParamFormState {
  if (Array.isArray(p.value)) {
    return { name: p.name, value_str: (p.value as unknown[]).join(', '), value_type: 'list' };
  }
  return { name: p.name, value_str: String(p.value ?? ''), value_type: 'string' };
}

function schemaDefaults(fields: ActionConfigFieldDef[]): Record<string, unknown> {
  const defaults: Record<string, unknown> = {};
  for (const field of fields) {
    if (field.default !== undefined && field.default !== null) {
      defaults[field.name] = field.default;
    }
  }
  return defaults;
}

function actionToFormState(a: ScheduledQueryAction): ActionFormState {
  return { action_type: a.action_type, action_config: { ...a.action_config } };
}


interface ActionConfigFieldProps {
  field: ActionConfigFieldDef;
  value: unknown;
  onChange: (val: unknown) => void;
}

function ActionConfigField({ field, value, onChange }: ActionConfigFieldProps) {
  const label = field.required ? `${field.label} *` : field.label;

  if (field.type === 'boolean') {
    return (
      <FormControlLabel
        control={
          <Checkbox
            checked={Boolean(value ?? field.default ?? false)}
            onChange={(e) => onChange(e.target.checked)}
            size="small"
          />
        }
        label={label}
      />
    );
  }

  if (field.type === 'select') {
    return (
      <FormControl size="small" fullWidth>
        <InputLabel>{label}</InputLabel>
        <Select
          label={label}
          value={String(value ?? field.default ?? '')}
          onChange={(e) => onChange(e.target.value)}
        >
          {(field.options ?? []).map((opt) => (
            <MenuItem key={opt} value={opt}>
              {opt}
            </MenuItem>
          ))}
        </Select>
        {field.description && (
          <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, ml: 1.5 }}>
            {field.description}
          </Typography>
        )}
      </FormControl>
    );
  }

  if (field.type === 'string_list') {
    // Store as comma-separated string; serialize to array on submit
    const displayVal = Array.isArray(value)
      ? (value as string[]).join(', ')
      : String(value ?? '');
    return (
      <TextField
        label={label}
        value={displayVal}
        onChange={(e) => onChange(e.target.value)}
        size="small"
        fullWidth
        helperText={field.description ?? 'Comma-separated values'}
      />
    );
  }

  if (field.type === 'text') {
    return (
      <TextField
        label={label}
        value={String(value ?? field.default ?? '')}
        onChange={(e) => onChange(e.target.value)}
        size="small"
        fullWidth
        multiline
        minRows={3}
        helperText={field.description}
        inputProps={{ style: { fontFamily: 'monospace', fontSize: 12 } }}
      />
    );
  }

  if (field.type === 'number') {
    return (
      <TextField
        label={label}
        type="number"
        value={String(value ?? field.default ?? '')}
        onChange={(e) => onChange(e.target.value === '' ? '' : Number(e.target.value))}
        size="small"
        fullWidth
        helperText={field.description}
      />
    );
  }

  // default: string
  return (
    <TextField
      label={label}
      value={String(value ?? field.default ?? '')}
      onChange={(e) => onChange(e.target.value)}
      size="small"
      fullWidth
      helperText={field.description}
    />
  );
}

interface ScheduledQueryDialogProps {
  open: boolean;
  onClose: () => void;
  onSave: (req: ScheduledQueryRequest) => Promise<void>;
  initial: ScheduledQueryItem | null;
}

function ScheduledQueryDialog({ open, onClose, onSave, initial }: ScheduledQueryDialogProps) {
  const { config } = useContext(ConfigContext);
  const actionTypes = config?.scheduled_query_action_types ?? [];
  const actionSchemas = config?.scheduled_query_action_schemas ?? {};
  const [name, setName] = useState(initial?.name ?? EMPTY_FORM.name);
  const [cypher, setCypher] = useState(initial?.cypher ?? EMPTY_FORM.cypher);
  const [enabled, setEnabled] = useState(initial?.enabled ?? EMPTY_FORM.enabled);
  const [triggerType, setTriggerType] = useState<TriggerType>(
    initial && initial.watch_scans.length > 0 ? 'watch_scans' : 'frequency'
  );
  const [frequency, setFrequency] = useState<string>(
    initial?.frequency != null ? String(initial.frequency) : '60'
  );
  const [watchScans, setWatchScans] = useState<ScheduledQueryWatchScan[]>(
    initial?.watch_scans ?? []
  );
  const [params, setParams] = useState<ParamFormState[]>(
    (initial?.params ?? []).map(paramToFormState)
  );
  const [actions, setActions] = useState<ActionFormState[]>(
    (initial?.actions ?? []).map(actionToFormState)
  );
  const [comment, setComment] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Reset form when dialog opens/closes or initial changes
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

    // Validate and serialize action configs
    const parsedActions: ScheduledQueryAction[] = [];
    for (const a of actions) {
      if (!a.action_type.trim()) {
        setError('All actions must have an action type.');
        return;
      }
      // Serialize string_list fields: convert comma-separated strings to arrays
      const serialized: Record<string, unknown> = {};
      const schema = actionSchemas[a.action_type] ?? [];
      const schemaMap = Object.fromEntries(schema.map((f) => [f.name, f]));
      for (const [key, val] of Object.entries(a.action_config)) {
        const fieldDef = schemaMap[key];
        if (fieldDef?.type === 'string_list' && typeof val === 'string') {
          serialized[key] = val.split(',').map((s) => s.trim()).filter(Boolean);
        } else {
          serialized[key] = val;
        }
      }
      parsedActions.push({ action_type: a.action_type, action_config: serialized });
    }

    const req: ScheduledQueryRequest = {
      name: name.trim(),
      cypher: cypher.trim(),
      params: params.map((p) => ({
        name: p.name,
        value:
          p.value_type === 'list'
            ? p.value_str.split(',').map((s) => s.trim()).filter(Boolean)
            : p.value_str,
      })),
      frequency: triggerType === 'frequency' ? (parseInt(frequency, 10) || null) : null,
      watch_scans: triggerType === 'watch_scans' ? watchScans : [],
      enabled,
      actions: parsedActions,
      comment: comment.trim() || null
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

  const addParam = () =>
    setParams((ps) => [...ps, { name: '', value_str: '', value_type: 'string' }]);
  const removeParam = (i: number) => setParams((ps) => ps.filter((_, idx) => idx !== i));
  const updateParamName = (i: number, val: string) =>
    setParams((ps) => ps.map((p, idx) => (idx === i ? { ...p, name: val } : p)));
  const updateParamValueStr = (i: number, val: string) =>
    setParams((ps) => ps.map((p, idx) => (idx === i ? { ...p, value_str: val } : p)));
  const toggleParamType = (i: number) =>
    setParams((ps) =>
      ps.map((p, idx) =>
        idx === i
          ? { ...p, value_type: p.value_type === 'string' ? 'list' : 'string' }
          : p
      )
    );

  const addWatchScan = () =>
    setWatchScans((ws) => [...ws, { grouptype: '.*', syncedtype: '.*', groupid: '.*' }]);
  const removeWatchScan = (i: number) => setWatchScans((ws) => ws.filter((_, idx) => idx !== i));
  const updateWatchScan = (i: number, field: keyof ScheduledQueryWatchScan, val: string) =>
    setWatchScans((ws) => ws.map((w, idx) => (idx === i ? { ...w, [field]: val } : w)));

  const addAction = () =>
    setActions((as) => [...as, { action_type: '', action_config: {} }]);
  const removeAction = (i: number) => setActions((as) => as.filter((_, idx) => idx !== i));
  const updateActionType = (i: number, val: string) => {
    const defaults = schemaDefaults(actionSchemas[val] ?? []);
    setActions((as) => as.map((a, idx) => (idx === i ? { action_type: val, action_config: defaults } : a)));
  };
  const updateActionConfigField = (i: number, fieldName: string, val: unknown) =>
    setActions((as) =>
      as.map((a, idx) =>
        idx === i ? { ...a, action_config: { ...a.action_config, [fieldName]: val } } : a
      )
    );

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="md" fullWidth>
      <DialogTitle>{initial ? 'Edit Scheduled Query' : 'New Scheduled Query'}</DialogTitle>
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
            label="Cypher Query"
            value={cypher}
            onChange={(e) => setCypher(e.target.value)}
            fullWidth
            required
            multiline
            minRows={4}
            inputProps={{ style: { fontFamily: 'monospace', fontSize: 13 } }}
          />
          <FormControlLabel
            control={<Switch checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />}
            label="Enabled"
          />

          <Divider />

          <FormControl>
            <FormLabel>Trigger</FormLabel>
            <RadioGroup
              row
              value={triggerType}
              onChange={(e) => setTriggerType(e.target.value as TriggerType)}
            >
              <FormControlLabel value="frequency" control={<Radio />} label="Fixed frequency" />
              <FormControlLabel value="watch_scans" control={<Radio />} label="Watch scans" />
            </RadioGroup>
          </FormControl>

          {triggerType === 'frequency' && (
            <TextField
              label="Frequency (minutes)"
              type="number"
              value={frequency}
              onChange={(e) => setFrequency(e.target.value)}
              inputProps={{ min: 1 }}
              sx={{ maxWidth: 220 }}
            />
          )}

          {triggerType === 'watch_scans' && (
            <Box>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                <Typography variant="subtitle2">Watch Scans</Typography>
                <IconButton size="small" onClick={addWatchScan}>
                  <AddCircleOutlineIcon fontSize="small" />
                </IconButton>
              </Box>
              {watchScans.length === 0 && (
                <Typography variant="body2" color="text.secondary">
                  No watch scans defined. Click + to add one.
                </Typography>
              )}
              {watchScans.map((ws, i) => (
                <Box key={i} sx={{ display: 'flex', gap: 1, mb: 1, alignItems: 'center' }}>
                  <TextField
                    label="grouptype"
                    value={ws.grouptype ?? ''}
                    onChange={(e) => updateWatchScan(i, 'grouptype', e.target.value)}
                    size="small"
                    sx={{ flex: 1 }}
                  />
                  <TextField
                    label="syncedtype"
                    value={ws.syncedtype ?? ''}
                    onChange={(e) => updateWatchScan(i, 'syncedtype', e.target.value)}
                    size="small"
                    sx={{ flex: 1 }}
                  />
                  <TextField
                    label="groupid"
                    value={ws.groupid ?? ''}
                    onChange={(e) => updateWatchScan(i, 'groupid', e.target.value)}
                    size="small"
                    sx={{ flex: 1 }}
                  />
                  <IconButton size="small" onClick={() => removeWatchScan(i)}>
                    <RemoveCircleOutlineIcon fontSize="small" />
                  </IconButton>
                </Box>
              ))}
            </Box>
          )}

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
              <Box key={i} sx={{ display: 'flex', gap: 1, mb: 1, alignItems: 'flex-start' }}>
                <TextField
                  label="Name"
                  value={p.name}
                  onChange={(e) => updateParamName(i, e.target.value)}
                  size="small"
                  sx={{ flex: 1 }}
                />
                <TextField
                  label={p.value_type === 'list' ? 'Values (comma-separated)' : 'Value'}
                  value={p.value_str}
                  onChange={(e) => updateParamValueStr(i, e.target.value)}
                  size="small"
                  sx={{ flex: 2 }}
                />
                <Tooltip title={p.value_type === 'list' ? 'Switch to single value' : 'Switch to list'}>
                  <Button
                    size="small"
                    variant={p.value_type === 'list' ? 'contained' : 'outlined'}
                    onClick={() => toggleParamType(i)}
                    sx={{ minWidth: 44, px: 1, mt: 0.25, flexShrink: 0, fontSize: 11 }}
                  >
                    list
                  </Button>
                </Tooltip>
                <IconButton size="small" onClick={() => removeParam(i)} sx={{ mt: 0.25 }}>
                  <RemoveCircleOutlineIcon fontSize="small" />
                </IconButton>
              </Box>
            ))}
          </Box>

          <Divider />

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

          <Divider />

          <Box>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
              <Typography variant="subtitle2">Actions</Typography>
              <IconButton size="small" onClick={addAction}>
                <AddCircleOutlineIcon fontSize="small" />
              </IconButton>
            </Box>
            {actions.length === 0 && (
              <Typography variant="body2" color="text.secondary">
                No actions. Click + to add one.
              </Typography>
            )}
            {actions.map((a, i) => {
              const schema = actionSchemas[a.action_type] ?? [];
              return (
                <Box
                  key={i}
                  sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 1, p: 1.5, mb: 1.5 }}
                >
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: schema.length > 0 ? 1.5 : 0 }}>
                    {actionTypes.length > 0 ? (
                      <FormControl size="small" sx={{ width: 220 }}>
                        <InputLabel>Action type</InputLabel>
                        <Select
                          label="Action type"
                          value={a.action_type}
                          onChange={(e) => updateActionType(i, e.target.value)}
                        >
                          {actionTypes.map((t) => (
                            <MenuItem key={t} value={t}>
                              {t}
                            </MenuItem>
                          ))}
                        </Select>
                      </FormControl>
                    ) : (
                      <TextField
                        label="Action type"
                        value={a.action_type}
                        onChange={(e) => updateActionType(i, e.target.value)}
                        size="small"
                        sx={{ width: 220 }}
                      />
                    )}
                    <Box sx={{ flex: 1 }} />
                    <IconButton size="small" onClick={() => removeAction(i)}>
                      <RemoveCircleOutlineIcon fontSize="small" />
                    </IconButton>
                  </Box>
                  {schema.length > 0 && (
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
                      {schema.map((field) => (
                        <ActionConfigField
                          key={field.name}
                          field={field}
                          value={a.action_config[field.name]}
                          onChange={(val) => updateActionConfigField(i, field.name, val)}
                        />
                      ))}
                    </Box>
                  )}
                </Box>
              );
            })}
          </Box>
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

function triggerSummary(item: ScheduledQueryItem): string {
  if (item.watch_scans.length > 0) return `Watch scans (${item.watch_scans.length})`;
  if (item.frequency != null) return `Every ${item.frequency} min`;
  return 'Not configured';
}

// ---------------------------------------------------------------------------
// Per-row overflow menu
// ---------------------------------------------------------------------------

interface RowMenuProps {
  item: ScheduledQueryItem;
  onEdit: () => void;
  onHistory: () => void;
  onDelete: () => void;
}

function RowMenu({ item: _item, onEdit, onHistory, onDelete }: RowMenuProps) {
  const [anchor, setAnchor] = useState<null | HTMLElement>(null);
  const hasPermission = usePermissions();
  const close = () => setAnchor(null);

  const canWrite = hasPermission('scheduled_queries:write');
  const canDelete = hasPermission('scheduled_queries:delete');

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
        <Tooltip title={!canWrite ? 'You do not have permission to edit scheduled queries' : ''} placement="left">
          <span>
            <MenuItem onClick={() => { onEdit(); close(); }} disabled={!canWrite}>
              <ListItemIcon><EditIcon fontSize="small" /></ListItemIcon>
              <ListItemText>Edit</ListItemText>
            </MenuItem>
          </span>
        </Tooltip>

        <MenuItem onClick={() => { onHistory(); close(); }}>
          <ListItemIcon><HistoryIcon fontSize="small" /></ListItemIcon>
          <ListItemText>View history</ListItemText>
        </MenuItem>

        <Divider />

        <Tooltip title={!canDelete ? 'You do not have permission to delete scheduled queries' : ''} placement="left">
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

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

function ScheduledQueries() {
  const navigate = useNavigate();
  const { scheduledQueries, loading, error, refresh } = useScheduledQueriesList();
  const { createScheduledQuery, updateScheduledQuery, deleteScheduledQuery } =
    useScheduledQueriesMutations();
  const hasPermission = usePermissions();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<ScheduledQueryItem | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<ScheduledQueryItem | null>(null);
  const [detailItem, setDetailItem] = useState<ScheduledQueryViewData | null>(null);
  const [deleting, setDeleting] = useState(false);

  const openCreate = () => {
    setEditTarget(null);
    setDialogOpen(true);
  };

  const openEdit = (item: ScheduledQueryItem) => {
    setEditTarget(item);
    setDialogOpen(true);
  };

  const handleSave = async (req: ScheduledQueryRequest) => {
    if (editTarget) {
      await updateScheduledQuery(editTarget.scheduled_query_id, req);
    } else {
      await createScheduledQuery(req);
    }
    refresh();
  };

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await deleteScheduledQuery(deleteTarget.scheduled_query_id);
      setDeleteTarget(null);
      refresh();
    } catch {
      // dialog stays open so user can retry
    } finally {
      setDeleting(false);
    }
  };

  return (
    <>
      <Box sx={{ p: 3 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
          <Typography variant="h1">Scheduled Queries</Typography>
          {hasPermission('scheduled_queries:write') && (
            <Button variant="contained" startIcon={<AddIcon />} onClick={openCreate}>
              New scheduled query
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
            <Typography>Failed to load scheduled queries</Typography>
          </Box>
        )}

        {!loading && !error && (
          <TableContainer component={Paper} variant="outlined">
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Name</TableCell>
                  <TableCell>Trigger</TableCell>
                  <TableCell>Actions</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Version</TableCell>
                  <TableCell>Latest Update</TableCell>
                  <TableCell>Updated By</TableCell>
                  <TableCell />
                </TableRow>
              </TableHead>
              <TableBody>
                {scheduledQueries.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={8}>
                      <Typography color="text.secondary" sx={{ py: 1 }}>
                        No scheduled queries yet. Create one above.
                      </Typography>
                    </TableCell>
                  </TableRow>
                )}
                {scheduledQueries.map((item) => (
                  <TableRow key={item.scheduled_query_id} hover>
                    <TableCell>
                      <Typography
                        variant="body2"
                        fontWeight={500}
                        sx={{ cursor: 'pointer', '&:hover': { textDecoration: 'underline' } }}
                        onClick={() => setDetailItem({
                          name: item.name,
                          cypher: item.cypher,
                          params: item.params,
                          frequency: item.frequency,
                          watch_scans: item.watch_scans,
                          enabled: item.enabled,
                          actions: item.actions,
                          last_run_status: item.last_run_status,
                          last_run_at: item.last_run_at,
                          last_errors: item.last_errors,
                        })}
                      >
                        {item.name}
                      </Typography>
                      <Typography
                        variant="caption"
                        color="text.secondary"
                        sx={{ fontFamily: 'monospace', display: 'block', maxWidth: 320, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                      >
                        {item.cypher.split('\n')[0]}
                      </Typography>
                    </TableCell>
                    <TableCell sx={{ color: 'text.secondary' }}>
                      {triggerSummary(item)}
                    </TableCell>
                    <TableCell>
                      {item.actions.length === 0 ? (
                        <Typography variant="body2" color="text.secondary">None</Typography>
                      ) : (
                        item.actions.map((a, i) => (
                          <Chip key={i} label={a.action_type} size="small" sx={{ mr: 0.5 }} />
                        ))
                      )}
                    </TableCell>
                    <TableCell>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Chip
                          label={item.enabled ? 'Enabled' : 'Disabled'}
                          color={item.enabled ? 'success' : 'default'}
                          size="small"
                        />
                        <Tooltip title={
                          item.last_run_status === 'success'
                            ? `Last run succeeded${item.last_run_at ? ` at ${new Date(item.last_run_at).toLocaleString()}` : ''}`
                            : item.last_run_status === 'failure'
                              ? `Last run failed${item.last_run_at ? ` at ${new Date(item.last_run_at).toLocaleString()}` : ''}`
                              : 'No runs yet'
                        }>
                          <FiberManualRecordIcon
                            sx={{
                              fontSize: 12,
                              color: item.last_run_status === 'success'
                                ? 'success.main'
                                : item.last_run_status === 'failure'
                                  ? 'error.main'
                                  : 'warning.main',
                            }}
                          />
                        </Tooltip>
                      </Box>
                    </TableCell>
                    <TableCell sx={{ color: 'text.secondary' }}>
                      v{item.current_version}
                    </TableCell>
                    <TableCell sx={{ color: 'text.secondary' }}>
                      {new Date(item.updated_at).toLocaleString()}
                    </TableCell>
                    <TableCell sx={{ color: 'text.secondary' }}>
                      {item.updated_by ? (
                        <UserDisplay userId={item.updated_by} />
                      ) : (
                        <UserDisplay userId={item.created_by} />
                      )}
                    </TableCell>
                    <TableCell align="right" sx={{ width: 48, pr: 1 }}>
                      <RowMenu
                        item={item}
                        onEdit={() => openEdit(item)}
                        onHistory={() => navigate(`/app/scheduled-queries/${item.scheduled_query_id}/history`)}
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

      <ScheduledQueryDialog
        key={editTarget?.scheduled_query_id ?? 'new'}
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        onSave={handleSave}
        initial={editTarget}
      />

      <ScheduledQueryDetailDialog
        open={!!detailItem}
        onClose={() => setDetailItem(null)}
        data={detailItem}
      />

      {/* Delete confirmation dialog */}
      <Dialog open={!!deleteTarget} onClose={() => setDeleteTarget(null)} maxWidth="xs" fullWidth>
        <DialogTitle>Delete scheduled query?</DialogTitle>
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

export default ScheduledQueries;
