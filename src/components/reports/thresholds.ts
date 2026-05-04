import type { Panel, PanelThreshold } from 'src/config.context';

/**
 * Curated color palette offered as quick-select swatches in the
 * ThresholdsEditor. Users can also pick any color via the native color
 * input embedded next to these.
 */
export const THRESHOLD_PRESET_COLORS: ReadonlyArray<{ label: string; hex: string }> = [
  { label: 'Red', hex: '#F44336' },
  { label: 'Orange', hex: '#FF9800' },
  { label: 'Yellow', hex: '#FFC107' },
  { label: 'Green', hex: '#4CAF50' },
  { label: 'Teal', hex: '#009688' },
  { label: 'Blue', hex: '#2196F3' },
  { label: 'Purple', hex: '#9C27B0' },
  { label: 'Pink', hex: '#E91E63' },
  { label: 'Grey', hex: '#9E9E9E' }
];

const LEGACY_PROGRESS_LOW = '#F44336';
const LEGACY_PROGRESS_FULL = '#4CAF50';
const LEGACY_COUNT_HIGH = '#F44336';

/**
 * Pick the color of the threshold with the highest ``value`` that is less
 * than or equal to ``metric``. Returns ``undefined`` when no threshold
 * matches — callers should fall back to the panel's default text color.
 */
export function resolveThresholdColor(
  metric: number,
  thresholds: PanelThreshold[] | undefined
): string | undefined {
  if (!thresholds || thresholds.length === 0) return undefined;
  let best: PanelThreshold | undefined;
  for (const t of thresholds) {
    if (t.value <= metric && (best === undefined || t.value > best.value)) {
      best = t;
    }
  }
  return best?.color;
}

/**
 * Convert a panel's legacy single ``threshold`` value into the equivalent
 * multi-threshold list.
 *
 * For ``count`` panels, the legacy semantic is "color the value when it
 * exceeds the threshold". This maps to a single threshold at the legacy
 * value with a red color.
 *
 * For ``progress`` panels, the legacy semantic is "below the threshold is
 * bad, 100% is great". This maps to a red threshold at 0 and a green
 * threshold at 100, with the legacy value sitting in the middle as a
 * neutral marker (no color override).
 */
export function migrateLegacyThreshold(panel: Panel): PanelThreshold[] {
  if (panel.threshold == null) return [];
  if (panel.type === 'progress') {
    const out: PanelThreshold[] = [{ value: 0, color: LEGACY_PROGRESS_LOW }];
    if (panel.threshold > 0 && panel.threshold < 100) {
      out.push({ value: panel.threshold, color: '' });
    }
    out.push({ value: 100, color: LEGACY_PROGRESS_FULL });
    return out.filter((t) => t.color !== '');
  }
  return [{ value: panel.threshold, color: LEGACY_COUNT_HIGH }];
}
