import fc from 'fast-check';
import { chartColorsFor } from 'src/theme/brand';

const HEX_COLOR_RE = /^#[0-9A-F]{6}$/;

describe('brand chart palette fuzzing', () => {
  it('cycles generated series indexes onto valid chart colors', () => {
    fc.assert(
      fc.property(
        fc.constantFrom<'light' | 'dark'>('light', 'dark'),
        fc.array(fc.integer({ min: 0, max: 1000 }), { minLength: 1, maxLength: 50 }),
        (mode, seriesIndexes) => {
          const colors = chartColorsFor(mode);

          expect(colors).toHaveLength(6);
          expect(new Set(colors).size).toBe(colors.length);

          for (const seriesIndex of seriesIndexes) {
            const color = colors[seriesIndex % colors.length];
            expect(color).toMatch(HEX_COLOR_RE);
          }
        }
      )
    );
  });
});
