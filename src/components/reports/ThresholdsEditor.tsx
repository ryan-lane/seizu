import { useState } from 'react';
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
    onChange([...thresholds, { value: 0, color: THRESHOLD_PRESET_COLORS[0].hex }]);
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
          // eslint-disable-next-line react/no-array-index-key
          <Stack key={idx} direction="row" spacing={1} alignItems="center">
            <TextField
              size="small"
              type="number"
              label="Value"
              value={Number.isFinite(t.value) ? t.value : ''}
              onChange={(e) => {
                const n = e.target.value === '' ? NaN : Number(e.target.value);
                setRow(idx, { ...t, value: Number.isFinite(n) ? n : 0 });
              }}
              sx={{ width: 120 }}
            />
            <ColorSwatchPicker
              color={t.color}
              onChange={(color) => setRow(idx, { ...t, color })}
            />
            <Box sx={{ flex: 1 }} />
            <Tooltip title="Remove threshold">
              <IconButton
                size="small"
                aria-label="Remove threshold"
                onClick={() => deleteRow(idx)}
              >
                <DeleteIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          </Stack>
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
