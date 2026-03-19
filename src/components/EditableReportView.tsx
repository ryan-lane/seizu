import { useState, useRef } from 'react';
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Box,
  Button,
  Chip,
  CircularProgress,
  Container,
  Divider,
  Grid,
  IconButton,
  Paper,
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

import { Report, Row, Panel } from 'src/config.context';
import PanelEditor, { EditablePanel } from 'src/components/reports/PanelEditor';

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
// Key-value editor for named queries
// ---------------------------------------------------------------------------

interface QueryRowProps {
  queryKey: string;
  value: string;
  onRename: (oldKey: string, newKey: string) => void;
  onValueChange: (key: string, value: string) => void;
  onDelete: (key: string) => void;
}

// Isolated row component so that local key-name state doesn't cause the
// parent to re-key the entire list on every keystroke.
function QueryRow({ queryKey, value, onRename, onValueChange, onDelete }: QueryRowProps) {
  const [localKey, setLocalKey] = useState(queryKey);

  // Keep local key in sync if the parent renames it externally
  if (localKey !== queryKey && document.activeElement?.getAttribute('data-query-key') !== queryKey) {
    setLocalKey(queryKey);
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
        value={value}
        onChange={(e) => onValueChange(queryKey, e.target.value)}
        sx={{ flex: 1 }}
        inputProps={{ style: { fontFamily: 'monospace', fontSize: '0.8rem' } }}
      />
      <Tooltip title="Delete query">
        <IconButton onClick={() => onDelete(queryKey)} size="small" sx={{ mt: 0.5 }}>
          <DeleteIcon fontSize="small" />
        </IconButton>
      </Tooltip>
    </Box>
  );
}

interface NamedQueryEditorProps {
  queries: Record<string, string>;
  onChange: (q: Record<string, string>) => void;
  onRename: (oldKey: string, newKey: string) => void;
}

function NamedQueryEditor({ queries, onChange, onRename }: NamedQueryEditorProps) {
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
  const [reportName, setReportName] = useState(report.name ?? '');
  const [namedQueries, setNamedQueries] = useState<Record<string, string>>(
    report.queries ?? {}
  );
  const [editableRows, setEditableRows] = useState<EditableRow[]>(
    toEditableRows(report.rows)
  );
  const [saveComment, setSaveComment] = useState('');
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

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

  async function handleSave() {
    setSaving(true);
    setSaveError(null);
    try {
      const updatedReport: Report = {
        ...report,
        name: reportName,
        queries: namedQueries,
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
      <Box
        sx={{
          position: 'sticky',
          top: 64,
          zIndex: 100,
          bgcolor: 'background.default',
          borderBottom: '1px solid',
          borderColor: 'divider',
          px: 3,
          py: 1.5,
          display: 'flex',
          alignItems: 'center',
          gap: 2
        }}
      >
        <Typography variant="subtitle1" fontWeight="medium" sx={{ flexShrink: 0 }}>
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
            startIcon={<CancelIcon />}
            onClick={onCancel}
            disabled={saving}
          >
            Cancel
          </Button>
          <Button
            variant="contained"
            startIcon={saving ? <CircularProgress size={16} /> : <SaveIcon />}
            onClick={handleSave}
            disabled={saving || !reportName.trim()}
          >
            Save version
          </Button>
        </Box>
      </Box>

      {/* Named queries section */}
      <Container maxWidth={false} sx={{ pt: 2, pb: 1 }}>
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
              onChange={setNamedQueries}
              onRename={handleQueryRename}
            />
          </AccordionDetails>
        </Accordion>
      </Container>

      {/* Rows with panels */}
      <DndContext sensors={sensors} onDragStart={onDragStart} onDragEnd={onDragEnd}>
        {editableRows.map((row) => (
          <Container key={row._id} maxWidth={false} sx={{ pb: 2 }}>
            <Paper elevation={1} sx={{ p: 2 }}>
              {/* Row header */}
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                <TextField
                  size="small"
                  label="Row name"
                  value={row.name}
                  onChange={(e) => renameRow(row._id, e.target.value)}
                  sx={{ flex: 1, maxWidth: 360 }}
                />
                <Box sx={{ flex: 1 }} />
                <Tooltip title="Add panel to this row">
                  <Button
                    size="small"
                    startIcon={<Add />}
                    onClick={() => openAddPanel(row._id)}
                  >
                    Add panel
                  </Button>
                </Tooltip>
                <Tooltip title="Delete row">
                  <IconButton
                    size="small"
                    color="error"
                    onClick={() => deleteRow(row._id)}
                  >
                    <DeleteIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
              </Box>
              <Divider sx={{ mb: 1.5 }} />

              {/* Panel grid */}
              <SortableContext
                items={row.panels.map((p) => p._id)}
                strategy={horizontalListSortingStrategy}
              >
                <DroppableRowArea rowId={row._id}>
                  <Grid container spacing={2}>
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
                            onEdit={() => openEditPanel(row._id, panel._id)}
                            onDelete={() => deletePanel(row._id, panel._id)}
                            onResize={(delta) => resizePanel(row._id, panel._id, delta)}
                          />
                        </Grid>
                      );
                    })}
                  </Grid>
                </DroppableRowArea>
              </SortableContext>
            </Paper>
          </Container>
        ))}

        <DragOverlay>
          {activePanel && <DragGhostCard panel={activePanel} />}
        </DragOverlay>
      </DndContext>

      {/* Add row */}
      <Container maxWidth={false} sx={{ pb: 3 }}>
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
    </>
  );
}

export default EditableReportView;
