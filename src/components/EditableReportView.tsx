import { useState, useRef, useEffect, memo, type Ref } from 'react';
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Box,
  Button,
  Chip,
  CircularProgress,
  Container,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  FormControl,
  Grid,
  IconButton,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Slider,
  Stack,
  TextField,
  Tooltip,
  Typography
} from '@mui/material';
import Add from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import EditIcon from '@mui/icons-material/Edit';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import DragIndicatorIcon from '@mui/icons-material/DragIndicator';
import RemoveIcon from '@mui/icons-material/Remove';
import SaveIcon from '@mui/icons-material/Save';
import CancelIcon from '@mui/icons-material/Cancel';

import {
  DndContext,
  DragEndEvent,
  DragOverlay,
  DragStartEvent,
  PointerSensor,
  useSensor,
  useSensors
} from '@dnd-kit/core';
import {
  SortableContext,
  horizontalListSortingStrategy,
  useSortable
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { useDroppable } from '@dnd-kit/core';

import { Report, Row, Panel, ReportInput, InputValue } from 'src/config.context';
import PanelEditor, { EditablePanel } from 'src/components/reports/PanelEditor';
import {
  DASHBOARD_NAVBAR_HEIGHT,
  DASHBOARD_SIDEBAR_WIDTH_VAR
} from 'src/components/dashboardLayoutConstants';
import { contentContainerSx } from 'src/theme/layout';

// ---------------------------------------------------------------------------
// Edit-state types (panels/rows get stable _id for DnD keys)
// ---------------------------------------------------------------------------

export interface EditableRow {
  _id: string;
  name: string;
  panels: EditablePanel[];
}

let _counter = 0;
function uid() {
  _counter += 1;
  return `id-${Date.now()}-${_counter}`;
}

function toEditableRows(rows: Row[]): EditableRow[] {
  return rows.map((row) => ({
    _id: uid(),
    name: row.name,
    panels: row.panels.map((p) => ({ ...p, _id: uid() }))
  }));
}

function fromEditableRows(rows: EditableRow[]): Row[] {
  return rows.map(({ _id: _rid, ...row }) => ({
    ...row,
    panels: row.panels.map(({ _id: _pid, ...panel }) => panel as Panel)
  }));
}

// ---------------------------------------------------------------------------
// Panel card shown inside the editable view
// ---------------------------------------------------------------------------

function PanelTypeChip({ type }: { type: string }) {
  return (
    <Chip
      label={type}
      size="small"
      variant="outlined"
      color="primary"
      sx={{ fontSize: '0.65rem', height: 20 }}
    />
  );
}

interface SortablePanelCardProps {
  panel: EditablePanel;
  onEdit: () => void;
  onDelete: () => void;
  onResize: (delta: number) => void;
}

function SortablePanelCard({ panel, onEdit, onDelete, onResize }: SortablePanelCardProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging
  } = useSortable({ id: panel._id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.4 : 1
  };

  const capped = Math.max(1, Math.min(12, panel.size ?? 3));
  const cypherPreview = panel.cypher
    ? panel.cypher.split('\n')[0].slice(0, 60) + (panel.cypher.length > 60 ? '…' : '')
    : panel.markdown
      ? 'Markdown content'
      : '(no query)';

  return (
    <div ref={setNodeRef} style={style}>
      <Paper
        variant="outlined"
        sx={{
          p: 1,
          height: '100%',
          minHeight: 120,
          display: 'flex',
          flexDirection: 'column',
          gap: 0.5,
          bgcolor: isDragging ? 'action.selected' : 'background.paper'
        }}
      >
        {/* Header row: drag handle + type + caption */}
        <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 0.5 }}>
          <Box
            {...attributes}
            {...listeners}
            sx={{ cursor: 'grab', color: 'text.secondary', flexShrink: 0, mt: 0.2 }}
          >
            <DragIndicatorIcon fontSize="small" />
          </Box>
          <Box sx={{ flex: 1, minWidth: 0 }}>
            <Stack direction="row" spacing={0.5} alignItems="center" flexWrap="wrap">
              <PanelTypeChip type={panel.type} />
              {panel.caption && (
                <Typography variant="caption" noWrap sx={{ maxWidth: 150 }}>
                  {panel.caption}
                </Typography>
              )}
            </Stack>
            <Typography
              variant="caption"
              color="text.secondary"
              sx={{
                display: 'block',
                fontFamily: 'monospace',
                fontSize: '0.65rem',
                mt: 0.5,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap'
              }}
            >
              {cypherPreview}
            </Typography>
          </Box>
        </Box>

        {/* Bottom toolbar: size + edit + delete */}
        <Box sx={{ display: 'flex', alignItems: 'center', mt: 'auto', gap: 0.25 }}>
          <Tooltip title="Decrease width">
            <span>
              <IconButton size="small" disabled={capped <= 1} onClick={() => onResize(-1)}>
                <RemoveIcon sx={{ fontSize: 14 }} />
              </IconButton>
            </span>
          </Tooltip>
          <Typography variant="caption" sx={{ minWidth: 16, textAlign: 'center' }}>
            {capped}
          </Typography>
          <Tooltip title="Increase width">
            <span>
              <IconButton size="small" disabled={capped >= 12} onClick={() => onResize(1)}>
                <Add sx={{ fontSize: 14 }} />
              </IconButton>
            </span>
          </Tooltip>
          <Box sx={{ flex: 1 }} />
          <Tooltip title="Edit panel">
            <IconButton size="small" onClick={onEdit}>
              <EditIcon sx={{ fontSize: 14 }} />
            </IconButton>
          </Tooltip>
          <Tooltip title="Delete panel">
            <IconButton size="small" color="error" onClick={onDelete}>
              <DeleteIcon sx={{ fontSize: 14 }} />
            </IconButton>
          </Tooltip>
        </Box>
      </Paper>
    </div>
  );
}

/** Ghost card shown in DragOverlay while dragging */
function DragGhostCard({ panel }: { panel: EditablePanel }) {
  return (
    <Paper
      elevation={6}
      sx={{ p: 1, minWidth: 160, opacity: 0.9 }}
    >
      <Stack direction="row" spacing={0.5} alignItems="center">
        <DragIndicatorIcon fontSize="small" color="action" />
        <PanelTypeChip type={panel.type} />
        {panel.caption && <Typography variant="caption">{panel.caption}</Typography>}
      </Stack>
    </Paper>
  );
}

// ---------------------------------------------------------------------------
// Droppable row container
// ---------------------------------------------------------------------------

function DroppableRowArea({ rowId, children }: { rowId: string; children: React.ReactNode }) {
  const { setNodeRef, isOver } = useDroppable({ id: rowId });
  return (
    <Box
      ref={setNodeRef}
      sx={{
        minHeight: 80,
        borderRadius: 1,
        bgcolor: isOver ? 'action.hover' : 'transparent',
        transition: 'background-color 150ms'
      }}
    >
      {children}
    </Box>
  );
}

// ---------------------------------------------------------------------------
// Inputs editor
// ---------------------------------------------------------------------------

const INPUT_TYPES = [
  { value: 'autocomplete', label: 'Autocomplete' },
  { value: 'text', label: 'Text' }
];

function emptyInput(): ReportInput {
  return { input_id: '', type: 'autocomplete', label: '', size: 3 };
}

interface InputCardProps {
  input: ReportInput;
  onEdit: () => void;
  onDelete: () => void;
  onResize: (delta: number) => void;
}

function InputCard({ input, onEdit, onDelete, onResize }: InputCardProps) {
  const capped = Math.max(1, Math.min(12, input.size ?? 3));
  return (
    <Paper
      variant="outlined"
      sx={{ p: 1.5, display: 'flex', alignItems: 'center', gap: 1 }}
    >
      <Box sx={{ flex: 1, minWidth: 0 }}>
        <Stack direction="row" spacing={0.5} alignItems="center" flexWrap="wrap">
          <Chip
            label={input.type}
            size="small"
            variant="outlined"
            color="secondary"
            sx={{ fontSize: '0.65rem', height: 20 }}
          />
          <Typography variant="body2" noWrap sx={{ fontWeight: 500 }}>
            {input.label || <em>no label</em>}
          </Typography>
          <Typography variant="caption" color="text.secondary" noWrap>
            id: {input.input_id || '—'}
          </Typography>
        </Stack>
      </Box>
      <Tooltip title="Decrease width">
        <span>
          <IconButton size="small" disabled={capped <= 1} onClick={() => onResize(-1)}>
            <RemoveIcon sx={{ fontSize: 14 }} />
          </IconButton>
        </span>
      </Tooltip>
      <Typography variant="caption" sx={{ minWidth: 16, textAlign: 'center' }}>
        {capped}
      </Typography>
      <Tooltip title="Increase width">
        <span>
          <IconButton size="small" disabled={capped >= 12} onClick={() => onResize(1)}>
            <Add sx={{ fontSize: 14 }} />
          </IconButton>
        </span>
      </Tooltip>
      <Tooltip title="Edit input">
        <IconButton size="small" onClick={onEdit}>
          <EditIcon sx={{ fontSize: 14 }} />
        </IconButton>
      </Tooltip>
      <Tooltip title="Delete input">
        <IconButton size="small" color="error" onClick={onDelete}>
          <DeleteIcon sx={{ fontSize: 14 }} />
        </IconButton>
      </Tooltip>
    </Paper>
  );
}

interface InputEditorDialogProps {
  open: boolean;
  input: ReportInput | null;
  onClose: () => void;
  onSave: (input: ReportInput) => void;
}

function InputEditorDialog({ open, input, onClose, onSave }: InputEditorDialogProps) {
  const [form, setForm] = useState<ReportInput>(emptyInput());

  useEffect(() => {
    setForm(input ? { ...input } : emptyInput());
  }, [input, open]);

  function set<K extends keyof ReportInput>(key: K, value: ReportInput[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function setDefault(field: keyof InputValue, value: string) {
    setForm((prev) => ({
      ...prev,
      default: { label: prev.default?.label ?? '', value: prev.default?.value ?? '', [field]: value }
    }));
  }

  const isAutocomplete = form.type === 'autocomplete';
  const canSave = form.input_id.trim() !== '' && form.label.trim() !== '';

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>{input ? 'Edit Input' : 'Add Input'}</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ mt: 1 }}>
          <FormControl fullWidth size="small">
            <InputLabel>Input type</InputLabel>
            <Select
              label="Input type"
              value={form.type}
              onChange={(e) => set('type', e.target.value)}
            >
              {INPUT_TYPES.map((t) => (
                <MenuItem key={t.value} value={t.value}>{t.label}</MenuItem>
              ))}
            </Select>
          </FormControl>

          <TextField
            fullWidth size="small" label="Input ID"
            value={form.input_id}
            onChange={(e) => set('input_id', e.target.value)}
            helperText="Referenced from panel params via input_id."
          />

          <TextField
            fullWidth size="small" label="Label"
            value={form.label}
            onChange={(e) => set('label', e.target.value)}
            helperText="Shown to the user above the input."
          />

          <Box>
            <Typography gutterBottom variant="body2">
              Size (grid columns: {form.size ?? 3})
            </Typography>
            <Slider
              min={1} max={12} step={1} marks
              value={form.size ?? 3}
              onChange={(_, v) => set('size', v as number)}
              valueLabelDisplay="auto"
            />
          </Box>

          {isAutocomplete && (
            <>
              <Divider />
              <TextField
                fullWidth size="small" label="Cypher (options query)"
                multiline minRows={3}
                value={form.cypher ?? ''}
                onChange={(e) => set('cypher', e.target.value || undefined)}
                inputProps={{ style: { fontFamily: 'monospace', fontSize: '0.8rem' } }}
                helperText="Query to populate the dropdown. Must return a 'value' column."
              />
            </>
          )}

          <Divider />
          <Typography variant="body2" fontWeight="medium">Default value</Typography>
          <Stack direction="row" spacing={1}>
            <TextField
              size="small" label="Default label"
              value={form.default?.label ?? ''}
              onChange={(e) => setDefault('label', e.target.value)}
              sx={{ flex: 1 }}
              helperText="Display label for the default."
            />
            <TextField
              size="small" label="Default value"
              value={form.default?.value ?? ''}
              onChange={(e) => setDefault('value', e.target.value)}
              sx={{ flex: 1 }}
              helperText="The parameter value sent to queries."
            />
          </Stack>
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button variant="contained" onClick={() => onSave(cleanInput(form))} disabled={!canSave}>
          Save Input
        </Button>
      </DialogActions>
    </Dialog>
  );
}

function cleanInput(input: ReportInput): ReportInput {
  const result: ReportInput = {
    input_id: input.input_id.trim(),
    type: input.type,
    label: input.label.trim()
  };
  if (input.size != null) result.size = Math.max(1, Math.min(12, input.size));
  if (input.cypher) result.cypher = input.cypher;
  if (input.default?.value) result.default = { label: input.default.label, value: input.default.value };
  return result;
}

// ---------------------------------------------------------------------------
// Key-value editor for named queries
// ---------------------------------------------------------------------------

interface QueryRowProps {
  queryKey: string;
  value: string;
  onRename: (oldKey: string, newKey: string) => void;
  onValueChange: (key: string, value: string) => void;
  onDraftValueChange: (key: string, value: string) => void;
  onDelete: (key: string) => void;
}

// Isolated row component so that local key-name state doesn't cause the
// parent to re-key the entire list on every keystroke.
function QueryRow({ queryKey, value, onRename, onValueChange, onDraftValueChange, onDelete }: QueryRowProps) {
  const [localKey, setLocalKey] = useState(queryKey);
  const [localValue, setLocalValue] = useState(value);

  // Keep local key in sync if the parent renames it externally
  if (localKey !== queryKey && document.activeElement?.getAttribute('data-query-key') !== queryKey) {
    setLocalKey(queryKey);
  }
  if (localValue !== value && document.activeElement?.getAttribute('data-query-value') !== queryKey) {
    setLocalValue(value);
  }

  return (
    <Box sx={{ display: 'flex', gap: 1, alignItems: 'flex-start' }}>
      <TextField
        size="small"
        label="Query name"
        value={localKey}
        onChange={(e) => setLocalKey(e.target.value)}
        onBlur={() => {
          const trimmed = localKey.trim();
          if (trimmed && trimmed !== queryKey) {
            onRename(queryKey, trimmed);
          } else {
            setLocalKey(queryKey); // revert if empty or unchanged
          }
        }}
        inputProps={{ 'data-query-key': queryKey }}
        sx={{ width: 220, flexShrink: 0 }}
        helperText="Used as cypher field in panels"
      />
      <TextField
        size="small"
        label="Cypher"
        multiline
        minRows={4}
        value={localValue}
        onChange={(e) => {
          setLocalValue(e.target.value);
          onDraftValueChange(queryKey, e.target.value);
        }}
        onBlur={() => {
          if (localValue !== value) onValueChange(queryKey, localValue);
        }}
        sx={{ flex: 1 }}
        inputProps={{ 'data-query-value': queryKey, style: { fontFamily: 'monospace', fontSize: '0.8rem' } }}
      />
      <Tooltip title="Delete query">
        <IconButton onClick={() => onDelete(queryKey)} size="small" sx={{ mt: 0.5 }}>
          <DeleteIcon fontSize="small" />
        </IconButton>
      </Tooltip>
    </Box>
  );
}

interface EditToolbarProps {
  initialReportName: string;
  saving: boolean;
  saveError: string | null;
  toolbarRef: Ref<HTMLDivElement>;
  onCancel: () => void;
  onSave: (reportName: string, saveComment: string) => void;
}

const EditToolbar = memo(function EditToolbar({
  initialReportName,
  saving,
  saveError,
  toolbarRef,
  onCancel,
  onSave
}: EditToolbarProps) {
  const [reportName, setReportName] = useState(initialReportName);
  const [saveComment, setSaveComment] = useState('');

  useEffect(() => {
    setReportName(initialReportName);
  }, [initialReportName]);

  return (
    <Box
      ref={toolbarRef}
      sx={{
        position: 'fixed',
        top: DASHBOARD_NAVBAR_HEIGHT,
        left: { xs: 0, lg: `var(${DASHBOARD_SIDEBAR_WIDTH_VAR})` },
        right: 0,
        zIndex: (theme) => theme.zIndex.appBar - 1,
        bgcolor: 'background.default',
        borderBottom: '1px solid',
        borderColor: 'divider',
        boxShadow: 1,
        ...contentContainerSx,
        py: 2,
        display: 'flex',
        alignItems: 'center',
        gap: 1.5
      }}
    >
      <Typography variant="body2" fontWeight="medium" sx={{ flexShrink: 0 }}>
        Editing report
      </Typography>
      <TextField
        size="small"
        label="Report name"
        value={reportName}
        onChange={(e) => setReportName(e.target.value)}
        sx={{ width: 260 }}
      />
      <TextField
        size="small"
        label="Save comment (optional)"
        value={saveComment}
        onChange={(e) => setSaveComment(e.target.value)}
        sx={{ flex: 1, maxWidth: 400 }}
      />
      {saveError && (
        <Typography variant="caption" color="error">
          {saveError}
        </Typography>
      )}
      <Box sx={{ ml: 'auto', display: 'flex', gap: 1 }}>
        <Button
          variant="outlined"
          size="small"
          startIcon={<CancelIcon />}
          onClick={onCancel}
          disabled={saving}
        >
          Cancel
        </Button>
        <Button
          variant="contained"
          size="small"
          startIcon={saving ? <CircularProgress size={16} /> : <SaveIcon />}
          onClick={() => onSave(reportName, saveComment)}
          disabled={saving || !reportName.trim()}
        >
          Save version
        </Button>
      </Box>
    </Box>
  );
});

interface EditableRowCardProps {
  row: EditableRow;
  rowIndex: number;
  onRename: (rowId: string, name: string) => void;
  onAddPanel: (rowId: string) => void;
  onDeleteRow: (rowId: string) => void;
  onEditPanel: (rowId: string, panelId: string) => void;
  onDeletePanel: (rowId: string, panelId: string) => void;
  onResizePanel: (rowId: string, panelId: string, delta: number) => void;
}

const EditableRowCard = memo(function EditableRowCard({
  row,
  rowIndex,
  onRename,
  onAddPanel,
  onDeleteRow,
  onEditPanel,
  onDeletePanel,
  onResizePanel
}: EditableRowCardProps) {
  const [rowName, setRowName] = useState(row.name);

  useEffect(() => {
    setRowName(row.name);
  }, [row._id, row.name]);

  const commitRowName = () => {
    const trimmed = rowName.trim();
    if (trimmed && trimmed !== row.name) {
      onRename(row._id, trimmed);
    } else if (!trimmed) {
      setRowName(row.name);
    }
  };

  return (
    <Container
      maxWidth={false}
      sx={{ ...contentContainerSx, pt: rowIndex === 0 ? 0.75 : 0, pb: 1.5 }}
    >
      <Paper elevation={1} sx={{ p: 1.5 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
          <TextField
            size="small"
            label="Row name"
            value={rowName}
            onChange={(e) => setRowName(e.target.value)}
            onBlur={commitRowName}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.currentTarget.blur();
              }
            }}
            sx={{ flex: 1, maxWidth: 360 }}
          />
          <Box sx={{ flex: 1 }} />
          <Tooltip title="Add panel to this row">
            <Button
              size="small"
              startIcon={<Add />}
              onClick={() => onAddPanel(row._id)}
            >
              Add panel
            </Button>
          </Tooltip>
          <Tooltip title="Delete row">
            <IconButton
              size="small"
              color="error"
              onClick={() => onDeleteRow(row._id)}
            >
              <DeleteIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
        <Divider sx={{ mb: 1.5 }} />

        <SortableContext
          items={row.panels.map((p) => p._id)}
          strategy={horizontalListSortingStrategy}
        >
          <DroppableRowArea rowId={row._id}>
            <Grid container spacing={1.5}>
              {row.panels.length === 0 && (
                <Grid size={12}>
                  <Typography variant="body2" color="text.secondary" sx={{ py: 2, px: 1 }}>
                    No panels yet. Click "Add panel" to add one, or drag a panel here.
                  </Typography>
                </Grid>
              )}
              {row.panels.map((panel) => {
                const size = Math.max(1, Math.min(12, panel.size ?? 3));
                return (
                  <Grid key={panel._id} size={{ lg: size, md: size, xl: size, xs: 12 }}>
                    <SortablePanelCard
                      panel={panel}
                      onEdit={() => onEditPanel(row._id, panel._id)}
                      onDelete={() => onDeletePanel(row._id, panel._id)}
                      onResize={(delta) => onResizePanel(row._id, panel._id, delta)}
                    />
                  </Grid>
                );
              })}
            </Grid>
          </DroppableRowArea>
        </SortableContext>
      </Paper>
    </Container>
  );
});

interface NamedQueryEditorProps {
  queries: Record<string, string>;
  onChange: (q: Record<string, string>) => void;
  onDraftValueChange: (key: string, value: string) => void;
  onRename: (oldKey: string, newKey: string) => void;
}

function NamedQueryEditor({ queries, onChange, onDraftValueChange, onRename }: NamedQueryEditorProps) {
  // Stable insertion-order list so React keys don't thrash when a key is renamed
  const [keyOrder, setKeyOrder] = useState<string[]>(() => Object.keys(queries));

  function renameKey(oldKey: string, newKey: string) {
    if (newKey === oldKey || newKey in queries) return;
    const next: Record<string, string> = {};
    for (const k of keyOrder) {
      next[k === oldKey ? newKey : k] = queries[k];
    }
    setKeyOrder((prev) => prev.map((k) => (k === oldKey ? newKey : k)));
    onChange(next);
    onRename(oldKey, newKey);
  }

  function updateValue(key: string, value: string) {
    onChange({ ...queries, [key]: value });
  }

  function addQuery() {
    const key = `query-${Date.now()}`;
    setKeyOrder((prev) => [...prev, key]);
    onChange({ ...queries, [key]: '' });
  }

  function removeQuery(key: string) {
    setKeyOrder((prev) => prev.filter((k) => k !== key));
    const next = { ...queries };
    delete next[key];
    onChange(next);
  }

  // Only show keys that still exist in the queries map (handles external resets)
  const orderedKeys = keyOrder.filter((k) => k in queries);

  return (
    <Stack spacing={2}>
      {orderedKeys.length === 0 && (
        <Typography variant="body2" color="text.secondary">
          No named queries yet. Add one below to reference it by key in panel Cypher fields.
        </Typography>
      )}
      {orderedKeys.map((key) => (
        <QueryRow
          key={key}
          queryKey={key}
          value={queries[key] ?? ''}
          onRename={renameKey}
          onValueChange={updateValue}
          onDraftValueChange={onDraftValueChange}
          onDelete={removeQuery}
        />
      ))}
      <Box>
        <Button size="small" startIcon={<Add />} onClick={addQuery}>
          Add named query
        </Button>
      </Box>
    </Stack>
  );
}

// ---------------------------------------------------------------------------
// Main EditableReportView
// ---------------------------------------------------------------------------

export interface EditableReportViewProps {
  report: Report;
  reportId: string;
  onSave: (report: Report, comment: string) => Promise<void>;
  onCancel: () => void;
}

function EditableReportView({ report, reportId: _reportId, onSave, onCancel }: EditableReportViewProps) {
  const [namedQueries, setNamedQueries] = useState<Record<string, string>>(
    report.queries ?? {}
  );
  const namedQueriesRef = useRef<Record<string, string>>(report.queries ?? {});
  const [editableRows, setEditableRows] = useState<EditableRow[]>(
    toEditableRows(report.rows)
  );
  const [editableInputs, setEditableInputs] = useState<ReportInput[]>(
    report.inputs ?? []
  );
  const [inputEditorOpen, setInputEditorOpen] = useState(false);
  const [editingInputIndex, setEditingInputIndex] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const toolbarRef = useRef<HTMLDivElement | null>(null);
  const [toolbarHeight, setToolbarHeight] = useState(72);

  // Panel editor dialog state
  const [editorOpen, setEditorOpen] = useState(false);
  const [editingPanelRef, setEditingPanelRef] = useState<{
    rowId: string;
    panelId: string | null; // null = new panel
  } | null>(null);
  const editingPanel = useRef<EditablePanel | null>(null);

  // DnD
  const [activePanel, setActivePanel] = useState<EditablePanel | null>(null);
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } })
  );

  function updateNamedQueries(next: Record<string, string>) {
    namedQueriesRef.current = next;
    setNamedQueries(next);
  }

  function updateNamedQueryDraft(key: string, value: string) {
    namedQueriesRef.current = { ...namedQueriesRef.current, [key]: value };
  }

  useEffect(() => {
    if (toolbarRef.current === null) return undefined;

    const updateToolbarHeight = () => {
      setToolbarHeight(toolbarRef.current?.offsetHeight ?? 72);
    };

    updateToolbarHeight();
    if (typeof ResizeObserver === 'undefined') return undefined;

    const observer = new ResizeObserver(updateToolbarHeight);
    observer.observe(toolbarRef.current);
    return () => observer.disconnect();
  }, []);

  // ---------------------------------------------------------------------------
  // Row operations
  // ---------------------------------------------------------------------------

  function handleQueryRename(oldKey: string, newKey: string) {
    setEditableRows((prev) =>
      prev.map((row) => ({
        ...row,
        panels: row.panels.map((panel) => ({
          ...panel,
          cypher: panel.cypher === oldKey ? newKey : panel.cypher,
          details_cypher: panel.details_cypher === oldKey ? newKey : panel.details_cypher
        }))
      }))
    );
  }

  // ---------------------------------------------------------------------------
  // Input operations
  // ---------------------------------------------------------------------------

  function openAddInput() {
    setEditingInputIndex(null);
    setInputEditorOpen(true);
  }

  function openEditInput(index: number) {
    setEditingInputIndex(index);
    setInputEditorOpen(true);
  }

  function handleInputSave(saved: ReportInput) {
    if (editingInputIndex === null) {
      setEditableInputs((prev) => [...prev, saved]);
    } else {
      setEditableInputs((prev) => prev.map((inp, i) => (i === editingInputIndex ? saved : inp)));
    }
    setInputEditorOpen(false);
  }

  function deleteInput(index: number) {
    setEditableInputs((prev) => prev.filter((_, i) => i !== index));
  }

  function resizeInput(index: number, delta: number) {
    setEditableInputs((prev) =>
      prev.map((inp, i) =>
        i === index ? { ...inp, size: Math.max(1, Math.min(12, (inp.size ?? 3) + delta)) } : inp
      )
    );
  }

  // ---------------------------------------------------------------------------

  function addRow() {
    setEditableRows((prev) => [
      ...prev,
      { _id: uid(), name: 'New Row', panels: [] }
    ]);
  }

  function deleteRow(rowId: string) {
    setEditableRows((prev) => prev.filter((r) => r._id !== rowId));
  }

  function renameRow(rowId: string, name: string) {
    setEditableRows((prev) =>
      prev.map((r) => (r._id === rowId ? { ...r, name } : r))
    );
  }

  // ---------------------------------------------------------------------------
  // Panel operations
  // ---------------------------------------------------------------------------

  function openAddPanel(rowId: string) {
    editingPanel.current = null;
    setEditingPanelRef({ rowId, panelId: null });
    setEditorOpen(true);
  }

  function openEditPanel(rowId: string, panelId: string) {
    const row = editableRows.find((r) => r._id === rowId);
    const panel = row?.panels.find((p) => p._id === panelId);
    if (!panel) return;
    editingPanel.current = panel;
    setEditingPanelRef({ rowId, panelId });
    setEditorOpen(true);
  }

  function handlePanelSave(saved: EditablePanel) {
    if (!editingPanelRef) return;
    const { rowId, panelId } = editingPanelRef;

    if (panelId === null) {
      // Add new
      const newPanel: EditablePanel = { ...saved, _id: uid() };
      setEditableRows((prev) =>
        prev.map((r) =>
          r._id === rowId ? { ...r, panels: [...r.panels, newPanel] } : r
        )
      );
    } else {
      // Update existing
      setEditableRows((prev) =>
        prev.map((r) =>
          r._id === rowId
            ? {
                ...r,
                panels: r.panels.map((p) => (p._id === panelId ? { ...saved, _id: panelId } : p))
              }
            : r
        )
      );
    }
    setEditorOpen(false);
  }

  function deletePanel(rowId: string, panelId: string) {
    setEditableRows((prev) =>
      prev.map((r) =>
        r._id === rowId ? { ...r, panels: r.panels.filter((p) => p._id !== panelId) } : r
      )
    );
  }

  function resizePanel(rowId: string, panelId: string, delta: number) {
    setEditableRows((prev) =>
      prev.map((r) =>
        r._id === rowId
          ? {
              ...r,
              panels: r.panels.map((p) =>
                p._id === panelId
                  ? { ...p, size: Math.max(1, Math.min(12, (p.size ?? 3) + delta)) }
                  : p
              )
            }
          : r
      )
    );
  }

  // ---------------------------------------------------------------------------
  // DnD handlers
  // ---------------------------------------------------------------------------

  function onDragStart({ active }: DragStartEvent) {
    for (const row of editableRows) {
      const found = row.panels.find((p) => p._id === String(active.id));
      if (found) {
        setActivePanel(found);
        return;
      }
    }
  }

  function onDragEnd({ active, over }: DragEndEvent) {
    setActivePanel(null);
    if (!over || active.id === over.id) return;

    const activeId = String(active.id);
    const overId = String(over.id);

    // Find source
    let sourceRowIdx = -1;
    let sourcePanelIdx = -1;
    for (let ri = 0; ri < editableRows.length; ri++) {
      const pi = editableRows[ri].panels.findIndex((p) => p._id === activeId);
      if (pi !== -1) {
        sourceRowIdx = ri;
        sourcePanelIdx = pi;
        break;
      }
    }
    if (sourceRowIdx === -1) return;

    const newRows = editableRows.map((r) => ({ ...r, panels: [...r.panels] }));
    const [movedPanel] = newRows[sourceRowIdx].panels.splice(sourcePanelIdx, 1);

    // Is overId a panel?
    let targetRowIdx = -1;
    let targetPanelIdx = -1;
    for (let ri = 0; ri < newRows.length; ri++) {
      const pi = newRows[ri].panels.findIndex((p) => p._id === overId);
      if (pi !== -1) {
        targetRowIdx = ri;
        targetPanelIdx = pi;
        break;
      }
    }

    if (targetRowIdx !== -1) {
      newRows[targetRowIdx].panels.splice(targetPanelIdx, 0, movedPanel);
    } else {
      // Is overId a row?
      const targetRowByIdIdx = newRows.findIndex((r) => r._id === overId);
      if (targetRowByIdIdx !== -1) {
        newRows[targetRowByIdIdx].panels.push(movedPanel);
      } else {
        // Restore
        newRows[sourceRowIdx].panels.splice(sourcePanelIdx, 0, movedPanel);
      }
    }

    setEditableRows(newRows);
  }

  // ---------------------------------------------------------------------------
  // Save
  // ---------------------------------------------------------------------------

  async function handleSave(reportName: string, saveComment: string) {
    setSaving(true);
    setSaveError(null);
    try {
      const updatedReport: Report = {
        ...report,
        name: reportName,
        queries: namedQueriesRef.current,
        inputs: editableInputs.length ? editableInputs : undefined,
        rows: fromEditableRows(editableRows)
      };
      await onSave(updatedReport, saveComment);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Failed to save');
      setSaving(false);
    }
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <>
      {/* Top toolbar */}
      <EditToolbar
        initialReportName={report.name ?? ''}
        saving={saving}
        saveError={saveError}
        toolbarRef={toolbarRef}
        onCancel={onCancel}
        onSave={handleSave}
      />
      <Box sx={{ height: toolbarHeight }} />

      {/* Named queries section */}
      <Container maxWidth={false} sx={{ ...contentContainerSx, pt: 1.5, pb: 1 }}>
        <Accordion variant="outlined" disableGutters defaultExpanded>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Typography variant="body2" fontWeight="medium">
                Named Queries
              </Typography>
              <Chip
                label={Object.keys(namedQueries).length}
                size="small"
                variant="outlined"
                sx={{ height: 18, fontSize: '0.7rem' }}
              />
            </Box>
          </AccordionSummary>
          <AccordionDetails>
            <NamedQueryEditor
              queries={namedQueries}
              onChange={updateNamedQueries}
              onDraftValueChange={updateNamedQueryDraft}
              onRename={handleQueryRename}
            />
          </AccordionDetails>
        </Accordion>
      </Container>

      {/* Inputs section */}
      <Container maxWidth={false} sx={{ ...contentContainerSx, pt: 0, pb: 1 }}>
        <Accordion variant="outlined" disableGutters defaultExpanded>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Typography variant="body2" fontWeight="medium">
                Inputs
              </Typography>
              <Chip
                label={editableInputs.length}
                size="small"
                variant="outlined"
                sx={{ height: 18, fontSize: '0.7rem' }}
              />
            </Box>
          </AccordionSummary>
          <AccordionDetails>
            <Stack spacing={1}>
              {editableInputs.length === 0 && (
                <Typography variant="body2" color="text.secondary">
                  No inputs yet. Add one below to let users filter panel queries.
                </Typography>
              )}
              {editableInputs.map((inp, i) => (
                // eslint-disable-next-line react/no-array-index-key
                <InputCard
                  key={i}
                  input={inp}
                  onEdit={() => openEditInput(i)}
                  onDelete={() => deleteInput(i)}
                  onResize={(delta) => resizeInput(i, delta)}
                />
              ))}
              <Box>
                <Button size="small" startIcon={<Add />} onClick={openAddInput}>
                  Add input
                </Button>
              </Box>
            </Stack>
          </AccordionDetails>
        </Accordion>
      </Container>

      {/* Rows with panels */}
      <DndContext sensors={sensors} onDragStart={onDragStart} onDragEnd={onDragEnd}>
        {editableRows.map((row, rowIndex) => (
          <EditableRowCard
            key={row._id}
            row={row}
            rowIndex={rowIndex}
            onRename={renameRow}
            onAddPanel={openAddPanel}
            onDeleteRow={deleteRow}
            onEditPanel={openEditPanel}
            onDeletePanel={deletePanel}
            onResizePanel={resizePanel}
          />
        ))}

        <DragOverlay>
          {activePanel && <DragGhostCard panel={activePanel} />}
        </DragOverlay>
      </DndContext>

      {/* Add row */}
      <Container maxWidth={false} sx={{ ...contentContainerSx, pb: 2.5 }}>
        <Button variant="outlined" startIcon={<Add />} onClick={addRow} fullWidth>
          Add Row
        </Button>
      </Container>

      {/* Panel editor dialog */}
      <PanelEditor
        open={editorOpen}
        panel={editingPanelRef?.panelId ? editingPanel.current : null}
        onClose={() => setEditorOpen(false)}
        onSave={handlePanelSave}
      />

      {/* Input editor dialog */}
      <InputEditorDialog
        open={inputEditorOpen}
        input={editingInputIndex !== null ? (editableInputs[editingInputIndex] ?? null) : null}
        onClose={() => setInputEditorOpen(false)}
        onSave={handleInputSave}
      />
    </>
  );
}

export default EditableReportView;
