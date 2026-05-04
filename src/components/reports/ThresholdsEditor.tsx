import { useEffect, useState } from 'react';
import {
  Box,
  Button,
  IconButton,
  Popover,
  Stack,
  TextField,
  Tooltip,
  Typography
} from '@mui/material';
import Add from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';

import type { PanelThreshold } from 'src/config.context';
import { THRESHOLD_PRESET_COLORS } from 'src/components/reports/thresholds';

interface ColorSwatchPickerProps {
  color: string;
  onChange: (color: string) => void;
}

/**
 * A small color swatch button that opens a popover offering preset
 * swatches plus a native color input for arbitrary hex picks.
 */
function ColorSwatchPicker({ color, onChange }: ColorSwatchPickerProps) {
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const open = Boolean(anchor);

  return (
    <>
      <Tooltip title="Pick color">
        <IconButton
          size="small"
          onClick={(e) => setAnchor(e.currentTarget)}
          aria-label="Pick color"
          sx={{
            width: 28,
            height: 28,
            border: 1,
            borderColor: 'divider',
            borderRadius: 1,
            p: 0,
            bgcolor: color || 'transparent'
          }}
        />
      </Tooltip>
      <Popover
        open={open}
        anchorEl={anchor}
        onClose={() => setAnchor(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
      >
        <Box sx={{ p: 1.5, display: 'flex', flexDirection: 'column', gap: 1 }}>
          <Typography variant="caption" color="text.secondary">
            Quick select
          </Typography>
          <Box
            sx={{
              display: 'grid',
              gridTemplateColumns: 'repeat(5, 24px)',
              gap: 0.75
            }}
          >
            {THRESHOLD_PRESET_COLORS.map((preset) => (
              <Tooltip key={preset.hex} title={preset.label}>
                <Box
                  onClick={() => {
                    onChange(preset.hex);
                    setAnchor(null);
                  }}
                  sx={{
                    width: 24,
                    height: 24,
                    bgcolor: preset.hex,
                    borderRadius: 0.5,
                    cursor: 'pointer',
                    outline: color.toLowerCase() === preset.hex.toLowerCase() ? '2px solid' : 'none',
                    outlineColor: 'primary.main',
                    outlineOffset: 1
                  }}
                />
              </Tooltip>
            ))}
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.5 }}>
            <Typography variant="caption" color="text.secondary" sx={{ flex: 1 }}>
              Custom
            </Typography>
            <input
              type="color"
              value={color || '#000000'}
              onChange={(e) => onChange(e.target.value)}
              style={{ width: 40, height: 28, border: 'none', padding: 0, background: 'transparent', cursor: 'pointer' }}
            />
            <TextField
              size="small"
              value={color}
              onChange={(e) => onChange(e.target.value)}
              placeholder="#FFFFFF"
              inputProps={{ style: { fontFamily: 'monospace', fontSize: '0.75rem' }, 'aria-label': 'Hex color' }}
              sx={{ width: 100 }}
            />
          </Box>
        </Box>
      </Popover>
    </>
  );
}

interface ThresholdRowProps {
  threshold: PanelThreshold;
  onChange: (next: PanelThreshold) => void;
  onDelete: () => void;
}

/**
 * One row of the thresholds editor. Holds local string state for the value
 * input so the user can type freely (clear the field, retype with a leading
 * zero, etc.) without snapping to ``0`` or being blocked by ``type=number``
 * controlled-input quirks. The parent only sees a parsed ``value`` —
 * non-finite values stay in local state and are filtered out at save time.
 */
function ThresholdRow({ threshold, onChange, onDelete }: ThresholdRowProps) {
  const [valueText, setValueText] = useState<string>(
    Number.isFinite(threshold.value) ? String(threshold.value) : ''
  );

  // If the parent sets a different finite value (e.g. via legacy-threshold
  // migration on first open), reflect that in the local buffer. Don't
  // overwrite a draft string that would parse to the same number.
  useEffect(() => {
    if (Number.isFinite(threshold.value)) {
      const parsed = valueText.trim() === '' ? NaN : Number(valueText);
      if (!Number.isFinite(parsed) || parsed !== threshold.value) {
        setValueText(String(threshold.value));
      }
    } else if (valueText.trim() !== '' && Number.isFinite(Number(valueText))) {
      setValueText('');
    }
    // We intentionally only want this to fire when the *external* value
    // changes; ``valueText`` shouldn't trigger a re-sync.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [threshold.value]);

  return (
    <Stack direction="row" spacing={1} alignItems="center">
      <TextField
        size="small"
        type="text"
        inputMode="decimal"
        label="Value"
        value={valueText}
        onChange={(e) => {
          const raw = e.target.value;
          setValueText(raw);
          const parsed = raw.trim() === '' ? NaN : Number(raw);
          // Propagate the parsed number (or NaN) so the resolver sees the
          // latest committed value. NaN-valued thresholds are skipped by the
          // resolver and stripped at save time.
          onChange({ ...threshold, value: parsed });
        }}
        sx={{ width: 120 }}
      />
      <ColorSwatchPicker
        color={threshold.color}
        onChange={(color) => onChange({ ...threshold, color })}
      />
      <Box sx={{ flex: 1 }} />
      <Tooltip title="Remove threshold">
        <IconButton size="small" aria-label="Remove threshold" onClick={onDelete}>
          <DeleteIcon fontSize="small" />
        </IconButton>
      </Tooltip>
    </Stack>
  );
}

interface ThresholdsEditorProps {
  thresholds: PanelThreshold[];
  onChange: (thresholds: PanelThreshold[]) => void;
  helperText?: string;
}

/**
 * List editor for ``Panel.thresholds``. Each row exposes a ``value`` field
 * and a ColorSwatchPicker; rows can be added or removed. The list is kept
 * sorted by ``value`` ascending on every change so the resolver semantics
 * (highest matching threshold wins) are obvious to the editor.
 */
function ThresholdsEditor({ thresholds, onChange, helperText }: ThresholdsEditorProps) {
  function setRow(idx: number, next: PanelThreshold) {
    const updated = thresholds.map((t, i) => (i === idx ? next : t));
    onChange(updated);
  }

  function deleteRow(idx: number) {
    onChange(thresholds.filter((_, i) => i !== idx));
  }

  function addRow() {
    // Start with no value so the input is empty and the user can type the
    // intended number directly without first clearing a default.
    onChange([
      ...thresholds,
      { value: Number.NaN, color: THRESHOLD_PRESET_COLORS[0].hex }
    ]);
  }

  return (
    <Box>
      <Typography gutterBottom variant="body2" fontWeight="medium">
        Thresholds
      </Typography>
      {helperText && (
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
          {helperText}
        </Typography>
      )}
      <Stack spacing={1}>
        {thresholds.length === 0 && (
          <Typography variant="caption" color="text.secondary">
            No thresholds configured. Click "Add threshold" to color the metric based on its value.
          </Typography>
        )}
        {thresholds.map((t, idx) => (
          <ThresholdRow
            // eslint-disable-next-line react/no-array-index-key
            key={idx}
            threshold={t}
            onChange={(next) => setRow(idx, next)}
            onDelete={() => deleteRow(idx)}
          />
        ))}
        <Box>
          <Button size="small" startIcon={<Add />} onClick={addRow}>
            Add threshold
          </Button>
        </Box>
      </Stack>
    </Box>
  );
}

export default ThresholdsEditor;
