import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Alert, Box, Button, Checkbox, Chip, CircularProgress, Dialog, DialogActions, DialogContent,
  DialogContentText, DialogTitle, Divider, FormControl, FormControlLabel, IconButton,
  InputLabel, ListItemIcon, ListItemText, Menu, MenuItem, Select, Switch,
  Table, TableBody, TableCell, TableHead, TableRow, TextField,
  Tooltip, Typography
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import AddCircleOutlineIcon from '@mui/icons-material/AddCircleOutline';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import DeleteIcon from '@mui/icons-material/Delete';
import EditIcon from '@mui/icons-material/Edit';
import HistoryIcon from '@mui/icons-material/History';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import RemoveCircleOutlineIcon from '@mui/icons-material/RemoveCircleOutline';
import Error from '@mui/icons-material/Error';
import {
  useSkillsList, useSkillMutations, SkillItem, CreateSkillRequest, UpdateSkillRequest
} from 'src/hooks/useSkillsetsApi';
import { ToolParamDef, useToolCatalog } from 'src/hooks/useToolsetsApi';
import ListTable, {
  ListTableColumn,
  listTableActionColumnSx,
  listTableMonoCellSx,
  listTablePrimaryCellSx,
  listTableSecondaryCellSx,
  listTableTruncateSx
} from 'src/components/ListTable';
import MarkdownEditor from 'src/components/MarkdownEditor';
import UserDisplay from 'src/components/UserDisplay';
import { usePermissions } from 'src/hooks/usePermissions';

const LOWER_SNAKE_ID = /^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$/;
const RAW_PLACEHOLDER_RE = /{{\s*([^{}]+?)\s*}}/g;

const descriptionColumnSx = { ...listTableSecondaryCellSx, width: '26%' };
const versionColumnSx = { ...listTableSecondaryCellSx, width: 88 };
const updatedAtColumnSx = { ...listTableSecondaryCellSx, width: 180 };
const updatedByColumnSx = { ...listTableSecondaryCellSx, width: 150 };

function skillStatus(skill: SkillItem): { enabled: boolean; label: string } {
  const effectiveEnabled = skill.effective_enabled ?? skill.enabled;
  if (effectiveEnabled) return { enabled: true, label: 'Enabled' };
  if (skill.disabled_reason === 'skillset_disabled') return { enabled: false, label: 'Disabled by skillset' };
  return { enabled: false, label: 'Disabled' };
}

type ParamFormState = {
  name: string;
  type: ToolParamDef['type'];
  description: string;
  required: boolean;
  default_str: string;
};

const EMPTY_PARAM: ParamFormState = { name: '', type: 'string', description: '', required: true, default_str: '' };

function paramToFormState(p: ToolParamDef): ParamFormState {
  return { name: p.name, type: p.type, description: p.description ?? '', required: p.required, default_str: p.default !== null && p.default !== undefined ? String(p.default) : '' };
}

function formStateToParam(p: ParamFormState): ToolParamDef {
  let defaultVal: unknown = null;
  if (p.default_str.trim() !== '') {
    if (p.type === 'integer') defaultVal = parseInt(p.default_str, 10);
    else if (p.type === 'float') defaultVal = parseFloat(p.default_str);
    else if (p.type === 'boolean') defaultVal = p.default_str.toLowerCase() === 'true';
    else defaultVal = p.default_str;
  }
  return { name: p.name, type: p.type, description: p.description, required: p.required, default: defaultVal };
}

interface SkillDialogProps {
  open: boolean;
  onClose: () => void;
  onSave: (req: CreateSkillRequest | UpdateSkillRequest) => Promise<void>;
  initial: SkillItem | null;
}

function SkillDialog({ open, onClose, onSave, initial }: SkillDialogProps) {
  const [skillId, setSkillId] = useState(initial?.skill_id ?? '');
  const [name, setName] = useState(initial?.name ?? '');
  const [description, setDescription] = useState(initial?.description ?? '');
  const [template, setTemplate] = useState(initial?.template ?? '');
  const [enabled, setEnabled] = useState(initial?.enabled ?? true);
  const [triggers, setTriggers] = useState<string[]>(initial?.triggers ?? []);
  const [triggerInput, setTriggerInput] = useState('');
  const [toolsRequired, setToolsRequired] = useState<string[]>(initial?.tools_required ?? []);
  const [params, setParams] = useState<ParamFormState[]>((initial?.parameters ?? []).map(paramToFormState));
  const [comment, setComment] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleClose = () => { setError(null); onClose(); };
  const addParam = () => setParams((ps) => [...ps, { ...EMPTY_PARAM }]);
  const addTrigger = () => {
    const value = triggerInput.trim();
    if (!value || triggers.includes(value)) return;
    setTriggers((items) => [...items, value]);
    setTriggerInput('');
  };
  const removeParam = (i: number) => setParams((ps) => ps.filter((_, idx) => idx !== i));
  const updateParam = <K extends keyof ParamFormState>(i: number, key: K, val: ParamFormState[K]) =>
    setParams((ps) => ps.map((p, idx) => (idx === i ? { ...p, [key]: val } : p)));

  const handleSave = async () => {
    setError(null);
    if (!name.trim()) { setError('Name is required.'); return; }
    if (!template.trim()) { setError('Template is required.'); return; }
    if (!initial && !LOWER_SNAKE_ID.test(skillId.trim())) { setError('ID must be lower_snake_case.'); return; }
    const paramNames = new Set<string>();
    for (const p of params) {
      if (!LOWER_SNAKE_ID.test(p.name.trim())) { setError('All parameter names must be lower_snake_case.'); return; }
      paramNames.add(p.name.trim());
    }
    for (const match of template.matchAll(RAW_PLACEHOLDER_RE)) {
      if (!LOWER_SNAKE_ID.test(match[1]) || !paramNames.has(match[1])) {
        setError(`Placeholder ${match[1]} must match a declared parameter.`);
        return;
      }
    }
    const req: CreateSkillRequest | UpdateSkillRequest = {
      ...(initial ? {} : { skill_id: skillId.trim() }),
      name: name.trim(),
      description: description.trim(),
      template,
      parameters: params.map(formStateToParam),
      triggers,
      tools_required: toolsRequired,
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

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="md" fullWidth>
      <DialogTitle>{initial ? 'Edit Skill' : 'New Skill'}</DialogTitle>
      <DialogContent dividers>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {!initial && <TextField label="ID" value={skillId} onChange={(e) => setSkillId(e.target.value)} fullWidth required helperText="lower_snake_case" />}
          <TextField label="Name" value={name} onChange={(e) => setName(e.target.value)} fullWidth required />
          <TextField label="Description" value={description} onChange={(e) => setDescription(e.target.value)} fullWidth multiline minRows={2} />
          <Box>
            <Typography variant="subtitle2" sx={{ mb: 1 }}>Template</Typography>
            <MarkdownEditor
              value={template}
              onChange={(value) => setTemplate(value ?? '')}
              sourceLabel="Template"
            />
          </Box>
          <Box>
            <Typography variant="subtitle2" sx={{ mb: 1 }}>Triggers</Typography>
            <Box sx={{ display: 'flex', gap: 1, mb: 1 }}>
              <TextField
                label="Trigger phrase"
                value={triggerInput}
                onChange={(e) => setTriggerInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addTrigger(); } }}
                size="small"
                fullWidth
              />
              <Button onClick={addTrigger}>Add</Button>
            </Box>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
              {triggers.map((trigger) => (
                <Chip key={trigger} label={trigger} onDelete={() => setTriggers((items) => items.filter((item) => item !== trigger))} size="small" />
              ))}
            </Box>
          </Box>
          <ToolRequirementsSelect value={toolsRequired} onChange={setToolsRequired} />
          <FormControlLabel control={<Switch checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />} label="Enabled" />
          <Divider />
          <Box>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
              <Typography variant="subtitle2">Parameters</Typography>
              <IconButton size="small" aria-label="Add parameter" onClick={addParam}><AddCircleOutlineIcon fontSize="small" /></IconButton>
            </Box>
            {params.map((p, i) => (
              <Box key={i} sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 1, p: 1.5, mb: 1.5, display: 'flex', flexDirection: 'column', gap: 1 }}>
                <Box sx={{ display: 'flex', gap: 1, alignItems: 'flex-start' }}>
                  <TextField label="Name" value={p.name} onChange={(e) => updateParam(i, 'name', e.target.value)} size="small" sx={{ flex: 2 }} required />
                  <FormControl size="small" sx={{ flex: 1 }}>
                    <InputLabel>Type</InputLabel>
                    <Select label="Type" value={p.type} onChange={(e) => updateParam(i, 'type', e.target.value as ToolParamDef['type'])}>
                      <MenuItem value="string">string</MenuItem>
                      <MenuItem value="integer">integer</MenuItem>
                      <MenuItem value="float">float</MenuItem>
                      <MenuItem value="boolean">boolean</MenuItem>
                    </Select>
                  </FormControl>
                  <TextField label="Default" value={p.default_str} onChange={(e) => updateParam(i, 'default_str', e.target.value)} size="small" sx={{ flex: 1 }} />
                  <FormControlLabel control={<Checkbox checked={p.required} onChange={(e) => updateParam(i, 'required', e.target.checked)} size="small" />} label="Required" sx={{ flexShrink: 0 }} />
                  <IconButton size="small" aria-label="Remove parameter" onClick={() => removeParam(i)} sx={{ mt: 0.5, flexShrink: 0 }}><RemoveCircleOutlineIcon fontSize="small" /></IconButton>
                </Box>
                <TextField label="Description" value={p.description} onChange={(e) => updateParam(i, 'description', e.target.value)} size="small" fullWidth />
              </Box>
            ))}
          </Box>
          {initial && <><Divider /><TextField label="Comment (optional)" value={comment} onChange={(e) => setComment(e.target.value)} fullWidth size="small" /></>}
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose} disabled={saving}>Cancel</Button>
        <Button onClick={handleSave} variant="contained" disabled={saving}>{saving ? <CircularProgress size={20} /> : 'Save'}</Button>
      </DialogActions>
    </Dialog>
  );
}

function ToolRequirementsSelect({ value, onChange }: {
  value: string[];
  onChange: (value: string[]) => void;
}) {
  const { tools } = useToolCatalog();
  return (
    <FormControl fullWidth size="small">
      <InputLabel>Tools Required</InputLabel>
      <Select
        multiple
        label="Tools Required"
        value={value}
        onChange={(e) => onChange(typeof e.target.value === 'string' ? e.target.value.split(',') : e.target.value)}
        renderValue={(selected) => (selected as string[]).join(', ')}
      >
        {tools.map((tool) => (
          <MenuItem key={tool.mcp_name} value={tool.mcp_name}>
            <Checkbox checked={value.includes(tool.mcp_name)} size="small" />
            <ListItemText primary={tool.mcp_name} secondary={`${tool.toolset_name} / ${tool.name}`} />
          </MenuItem>
        ))}
      </Select>
    </FormControl>
  );
}

function SkillDetailDialog({ open, onClose, skill }: {
  open: boolean;
  onClose: () => void;
  skill: SkillItem | null;
}) {
  if (!skill) return null;
  const status = skillStatus(skill);
  const triggers = skill.triggers ?? [];
  const toolsRequired = skill.tools_required ?? [];
  const parameters = skill.parameters ?? [];

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>{skill.name}</DialogTitle>
      <DialogContent dividers>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <Box>
            <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 0.5 }}>Slug</Typography>
            <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>{skill.skill_id}</Typography>
          </Box>
          <Box>
            <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 0.5 }}>Status</Typography>
            <Chip label={status.label} color={status.enabled ? 'success' : 'default'} size="small" />
          </Box>
          {skill.description && (
            <Box>
              <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 0.5 }}>Description</Typography>
              <Typography variant="body2">{skill.description}</Typography>
            </Box>
          )}
          {triggers.length > 0 && (
            <Box>
              <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 0.5 }}>Triggers</Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                {triggers.map((trigger) => <Chip key={trigger} label={trigger} size="small" />)}
              </Box>
            </Box>
          )}
          {toolsRequired.length > 0 && (
            <Box>
              <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 0.5 }}>Tools Required</Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                {toolsRequired.map((tool) => <Chip key={tool} label={tool} size="small" variant="outlined" />)}
              </Box>
            </Box>
          )}
          <Box>
            <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 0.5 }}>Template</Typography>
            <Box component="pre" sx={{ bgcolor: 'action.hover', p: 2, borderRadius: 1, whiteSpace: 'pre-wrap', wordBreak: 'break-word', m: 0, fontFamily: 'monospace', fontSize: 13 }}>{skill.template}</Box>
          </Box>
          <Box>
            <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 0.5 }}>Parameters</Typography>
            {parameters.length === 0 ? (
              <Typography variant="body2" color="text.secondary">No parameters.</Typography>
            ) : (
              <Table size="small">
                <TableHead><TableRow><TableCell>Name</TableCell><TableCell>Type</TableCell><TableCell>Required</TableCell><TableCell>Default</TableCell><TableCell>Description</TableCell></TableRow></TableHead>
                <TableBody>
                  {parameters.map((param) => (
                    <TableRow key={param.name}>
                      <TableCell sx={{ fontFamily: 'monospace', fontWeight: 600 }}>{param.name}</TableCell>
                      <TableCell>{param.type}</TableCell>
                      <TableCell sx={{ color: 'text.secondary' }}>{param.required ? 'Yes' : 'No'}</TableCell>
                      <TableCell sx={{ color: 'text.secondary', fontFamily: 'monospace' }}>{param.default !== null && param.default !== undefined ? String(param.default) : '-'}</TableCell>
                      <TableCell sx={{ color: 'text.secondary' }}>{param.description || '-'}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
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

function initialRenderValues(skill: SkillItem | null): Record<string, string> {
  const values: Record<string, string> = {};
  for (const param of skill?.parameters ?? []) {
    values[param.name] = param.default !== null && param.default !== undefined ? String(param.default) : '';
  }
  return values;
}

function buildRenderArguments(parameters: ToolParamDef[], values: Record<string, string>): {
  arguments: Record<string, unknown>;
  error: string | null;
} {
  const args: Record<string, unknown> = {};
  for (const param of parameters) {
    const rawValue = values[param.name] ?? '';
    const value = rawValue.trim();
    if (value === '') {
      if (param.required) return { arguments: {}, error: `${param.name} is required.` };
      continue;
    }
    if (param.type === 'integer') {
      if (!/^-?\d+$/.test(value)) return { arguments: {}, error: `${param.name} must be an integer.` };
      args[param.name] = parseInt(value, 10);
    } else if (param.type === 'float') {
      const parsed = Number(value);
      if (!Number.isFinite(parsed)) return { arguments: {}, error: `${param.name} must be a number.` };
      args[param.name] = parsed;
    } else if (param.type === 'boolean') {
      if (value !== 'true' && value !== 'false') return { arguments: {}, error: `${param.name} must be true or false.` };
      args[param.name] = value === 'true';
    } else {
      args[param.name] = rawValue;
    }
  }
  return { arguments: args, error: null };
}

function SkillRenderDialog({ skill, onClose, onRender }: {
  skill: SkillItem | null;
  onClose: () => void;
  onRender: (skillId: string, args: Record<string, unknown>) => Promise<{ text: string }>;
}) {
  const [values, setValues] = useState<Record<string, string>>({});
  const [renderText, setRenderText] = useState('');
  const [renderError, setRenderError] = useState<string | null>(null);
  const [rendering, setRendering] = useState(false);
  const parameters = skill?.parameters ?? [];

  useEffect(() => {
    setValues(initialRenderValues(skill));
    setRenderText('');
    setRenderError(null);
    setRendering(false);
  }, [skill]);

  const updateValue = (name: string, value: string) => {
    setValues((current) => ({ ...current, [name]: value }));
  };

  const runRender = async () => {
    if (!skill) return;
    setRenderError(null);
    const built = buildRenderArguments(parameters, values);
    if (built.error) {
      setRenderError(built.error);
      return;
    }
    setRendering(true);
    try {
      const result = await onRender(skill.skill_id, built.arguments);
      setRenderText(result.text);
    } catch (err) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      setRenderError((err as any)?.message ?? 'Failed to render.');
    } finally {
      setRendering(false);
    }
  };

  return (
    <Dialog open={!!skill} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>Render skill</DialogTitle>
      <DialogContent dividers>
        {renderError && <Alert severity="error" sx={{ mb: 2 }}>{renderError}</Alert>}
        {parameters.length === 0 ? (
          <Typography color="text.secondary" sx={{ mb: 2 }}>This skill does not define parameters.</Typography>
        ) : (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mb: 2 }}>
            {parameters.map((param) => (
              <Box key={param.name}>
                {param.type === 'boolean' ? (
                  <FormControl fullWidth size="small" required={param.required}>
                    <InputLabel>{param.name}</InputLabel>
                    <Select
                      label={param.name}
                      value={values[param.name] ?? ''}
                      onChange={(e) => updateValue(param.name, e.target.value)}
                    >
                      {!param.required && <MenuItem value=""><em>Use default</em></MenuItem>}
                      <MenuItem value="true">true</MenuItem>
                      <MenuItem value="false">false</MenuItem>
                    </Select>
                  </FormControl>
                ) : (
                  <TextField
                    label={param.name}
                    value={values[param.name] ?? ''}
                    onChange={(e) => updateValue(param.name, e.target.value)}
                    fullWidth
                    required={param.required}
                    size="small"
                    type={param.type === 'integer' || param.type === 'float' ? 'number' : 'text'}
                    inputProps={param.type === 'integer' ? { step: 1 } : param.type === 'float' ? { step: 'any' } : undefined}
                  />
                )}
                <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', mt: 0.75, flexWrap: 'wrap' }}>
                  <Chip label={param.required ? 'Required' : 'Optional'} size="small" color={param.required ? 'primary' : 'default'} variant="outlined" />
                  <Chip label={param.type} size="small" variant="outlined" />
                  {param.default !== null && param.default !== undefined && <Typography variant="caption" color="text.secondary">{`Default: ${String(param.default)}`}</Typography>}
                </Box>
                {param.description && <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>{param.description}</Typography>}
              </Box>
            ))}
          </Box>
        )}
        <Box component="pre" sx={{ bgcolor: 'action.hover', p: 2, borderRadius: 1, whiteSpace: 'pre-wrap', wordBreak: 'break-word', minHeight: 96 }}>{renderText}</Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={rendering}>Close</Button>
        <Button variant="contained" startIcon={<PlayArrowIcon />} onClick={runRender} disabled={rendering}>{rendering ? <CircularProgress size={20} /> : 'Render'}</Button>
      </DialogActions>
    </Dialog>
  );
}

function SkillsetSkills() {
  const { skillsetId } = useParams();
  const navigate = useNavigate();
  const { skills, loading, error, refresh } = useSkillsList(skillsetId ?? null);
  const { createSkill, updateSkill, deleteSkill, renderSkill } = useSkillMutations(skillsetId ?? '');
  const hasPermission = usePermissions();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<SkillItem | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<SkillItem | null>(null);
  const [renderTarget, setRenderTarget] = useState<SkillItem | null>(null);
  const [detailTarget, setDetailTarget] = useState<SkillItem | null>(null);
  const [deleting, setDeleting] = useState(false);

  const handleSave = async (req: CreateSkillRequest | UpdateSkillRequest) => {
    if (editTarget) await updateSkill(editTarget.skill_id, req as UpdateSkillRequest);
    else await createSkill(req as CreateSkillRequest);
    refresh();
  };

  const columns: ListTableColumn<SkillItem>[] = [
    {
      key: 'name',
      label: 'Name',
      cellSx: listTablePrimaryCellSx,
      render: (skill) => (
        <Typography
          variant="body2"
          fontWeight={500}
          sx={[
            { cursor: 'pointer', '&:hover': { textDecoration: 'underline' } },
            listTableTruncateSx
          ]}
          onClick={() => setDetailTarget(skill)}
        >
          {skill.name}
        </Typography>
      )
    },
    {
      key: 'slug',
      label: 'Slug',
      hideBelow: 'lg',
      cellSx: listTableMonoCellSx,
      render: (skill) => skill.skill_id
    },
    {
      key: 'description',
      label: 'Description',
      hideBelow: 'md',
      cellSx: descriptionColumnSx,
      render: (skill) => (
        <Typography variant="body2" color="text.secondary" sx={listTableTruncateSx}>
          {skill.description || '-'}
        </Typography>
      )
    },
    {
      key: 'status',
      label: 'Status',
      render: (skill) => (
        <Chip
          label={skillStatus(skill).label}
          color={skillStatus(skill).enabled ? 'success' : 'default'}
          size="small"
        />
      )
    },
    {
      key: 'version',
      label: 'Version',
      hideBelow: 'sm',
      cellSx: versionColumnSx,
      render: (skill) => `v${skill.current_version}`
    },
    {
      key: 'updated_at',
      label: 'Last updated',
      hideBelow: 'xl',
      cellSx: updatedAtColumnSx,
      render: (skill) => skill.updated_at ? new Date(skill.updated_at).toLocaleString() : '-'
    },
    {
      key: 'updated_by',
      label: 'Updated by',
      hideBelow: 'lg',
      cellSx: updatedByColumnSx,
      render: (skill) => skill.updated_by ? <UserDisplay userId={skill.updated_by} /> : <UserDisplay userId={skill.created_by} />
    },
    {
      key: 'actions',
      align: 'right',
      cellSx: listTableActionColumnSx,
      render: (skill) => (
        <SkillRowMenu
          canWrite={hasPermission('skills:write')}
          canDelete={hasPermission('skills:delete')}
          canRender={hasPermission('skills:render') && skillStatus(skill).enabled}
          onDetail={() => setDetailTarget(skill)}
          onEdit={() => { setEditTarget(skill); setDialogOpen(true); }}
          onRender={() => setRenderTarget(skill)}
          onHistory={() => navigate(`/app/skillsets/${skillsetId}/skills/${skill.skill_id}/history`)}
          onDelete={() => setDeleteTarget(skill)}
        />
      )
    }
  ];

  return (
    <>
      <Box sx={{ p: 3 }}>
        <Button startIcon={<ArrowBackIcon />} onClick={() => navigate('/app/skillsets')} sx={{ mb: 2 }}>Back to skillsets</Button>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
          <Typography variant="h1">Skills</Typography>
          {hasPermission('skills:write') && <Button variant="contained" startIcon={<AddIcon />} onClick={() => { setEditTarget(null); setDialogOpen(true); }}>New skill</Button>}
        </Box>
        {loading && <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}><CircularProgress /></Box>}
        {error && <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}><Error /><Typography>Failed to load skills</Typography></Box>}
        {!loading && !error && (
          <ListTable
            rows={skills}
            columns={columns}
            getRowKey={(skill) => skill.skill_id}
            emptyMessage="No skills yet. Create one above."
          />
        )}
      </Box>
      <SkillDialog key={editTarget?.skill_id ?? 'new'} open={dialogOpen} onClose={() => setDialogOpen(false)} onSave={handleSave} initial={editTarget} />
      <Dialog open={!!deleteTarget} onClose={() => setDeleteTarget(null)} maxWidth="xs" fullWidth>
        <DialogTitle>Delete skill?</DialogTitle>
        <DialogContent><DialogContentText>Permanently delete <strong>{deleteTarget?.name}</strong> and all its versions?</DialogContentText></DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteTarget(null)} disabled={deleting}>Cancel</Button>
          <Button variant="contained" color="error" disabled={deleting} onClick={async () => { if (!deleteTarget) return; setDeleting(true); try { await deleteSkill(deleteTarget.skill_id); setDeleteTarget(null); refresh(); } finally { setDeleting(false); } }}>{deleting ? <CircularProgress size={20} /> : 'Delete'}</Button>
        </DialogActions>
      </Dialog>
      <SkillDetailDialog open={!!detailTarget} onClose={() => setDetailTarget(null)} skill={detailTarget} />
      <SkillRenderDialog skill={renderTarget} onClose={() => setRenderTarget(null)} onRender={renderSkill} />
    </>
  );
}

function SkillRowMenu({ canWrite, canDelete, canRender, onDetail, onEdit, onRender, onHistory, onDelete }: {
  canWrite: boolean; canDelete: boolean; canRender: boolean; onDetail: () => void; onEdit: () => void; onRender: () => void; onHistory: () => void; onDelete: () => void;
}) {
  const [anchor, setAnchor] = useState<null | HTMLElement>(null);
  const close = () => setAnchor(null);
  return (
    <>
      <Tooltip title="More actions"><IconButton size="small" onClick={(e) => setAnchor(e.currentTarget)}><MoreVertIcon fontSize="small" /></IconButton></Tooltip>
      <Menu anchorEl={anchor} open={!!anchor} onClose={close} anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }} transformOrigin={{ vertical: 'top', horizontal: 'right' }} slotProps={{ paper: { sx: { minWidth: 180 } } }}>
        <MenuItem onClick={() => { onDetail(); close(); }}><ListItemIcon><HistoryIcon fontSize="small" /></ListItemIcon><ListItemText>View detail</ListItemText></MenuItem>
        <MenuItem onClick={() => { onRender(); close(); }} disabled={!canRender}><ListItemIcon><PlayArrowIcon fontSize="small" /></ListItemIcon><ListItemText>Render</ListItemText></MenuItem>
        <MenuItem onClick={() => { onEdit(); close(); }} disabled={!canWrite}><ListItemIcon><EditIcon fontSize="small" /></ListItemIcon><ListItemText>Edit</ListItemText></MenuItem>
        <MenuItem onClick={() => { onHistory(); close(); }}><ListItemIcon><HistoryIcon fontSize="small" /></ListItemIcon><ListItemText>View history</ListItemText></MenuItem>
        <Divider />
        <MenuItem onClick={() => { onDelete(); close(); }} disabled={!canDelete} sx={{ color: canDelete ? 'error.main' : undefined }}><ListItemIcon><DeleteIcon fontSize="small" color={canDelete ? 'error' : 'disabled'} /></ListItemIcon><ListItemText>Delete</ListItemText></MenuItem>
      </Menu>
    </>
  );
}

export default SkillsetSkills;
