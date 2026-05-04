import type { Panel } from 'src/config.context';
import {
  migrateLegacyThreshold,
  resolveThresholdColor,
  THRESHOLD_PRESET_COLORS
} from '../thresholds';

describe('resolveThresholdColor', () => {
  it('returns undefined when no thresholds are configured', () => {
    expect(resolveThresholdColor(50, undefined)).toBeUndefined();
    expect(resolveThresholdColor(50, [])).toBeUndefined();
  });

  it('returns undefined when the metric is below all thresholds', () => {
    const thresholds = [
      { value: 50, color: '#FF0000' },
      { value: 100, color: '#00FF00' }
    ];
    expect(resolveThresholdColor(10, thresholds)).toBeUndefined();
  });

  it('returns the color of the highest matching threshold', () => {
    const thresholds = [
      { value: 0, color: '#FF0000' },
      { value: 70, color: '#FFC107' },
      { value: 100, color: '#4CAF50' }
    ];
    expect(resolveThresholdColor(0, thresholds)).toBe('#FF0000');
    expect(resolveThresholdColor(50, thresholds)).toBe('#FF0000');
    expect(resolveThresholdColor(70, thresholds)).toBe('#FFC107');
    expect(resolveThresholdColor(99, thresholds)).toBe('#FFC107');
    expect(resolveThresholdColor(100, thresholds)).toBe('#4CAF50');
    expect(resolveThresholdColor(120, thresholds)).toBe('#4CAF50');
  });

  it('does not assume thresholds are pre-sorted', () => {
    const thresholds = [
      { value: 100, color: '#00FF00' },
      { value: 0, color: '#FF0000' }
    ];
    expect(resolveThresholdColor(100, thresholds)).toBe('#00FF00');
    expect(resolveThresholdColor(50, thresholds)).toBe('#FF0000');
  });
});

describe('migrateLegacyThreshold', () => {
  it('returns an empty list when no legacy threshold is set', () => {
    const panel: Panel = { type: 'count' };
    expect(migrateLegacyThreshold(panel)).toEqual([]);
  });

  it('maps a count threshold to a single red threshold', () => {
    const panel: Panel = { type: 'count', threshold: 1000 };
    expect(migrateLegacyThreshold(panel)).toEqual([
      { value: 1000, color: '#F44336' }
    ]);
  });

  it('maps a progress threshold to red-at-zero plus green-at-hundred', () => {
    const panel: Panel = { type: 'progress', threshold: 70 };
    expect(migrateLegacyThreshold(panel)).toEqual([
      { value: 0, color: '#F44336' },
      { value: 100, color: '#4CAF50' }
    ]);
  });
});

describe('THRESHOLD_PRESET_COLORS', () => {
  it('exposes a non-empty palette of swatches', () => {
    expect(THRESHOLD_PRESET_COLORS.length).toBeGreaterThan(0);
    for (const preset of THRESHOLD_PRESET_COLORS) {
      expect(preset.label).toBeTruthy();
      expect(preset.hex).toMatch(/^#[0-9A-Fa-f]{6}$/);
    }
  });
});
