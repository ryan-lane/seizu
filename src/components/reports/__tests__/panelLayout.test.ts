import { Panel } from 'src/config.context';
import {
  buildResponsiveLayouts,
  defaultMinHeight,
  defaultPanelHeight,
  defaultPanelWidth,
  deriveRowLayout
} from '../panelLayout';

describe('defaultPanelHeight', () => {
  it('returns the per-type default for known panel types', () => {
    expect(defaultPanelHeight('count')).toBe(4);
    expect(defaultPanelHeight('progress')).toBe(4);
    expect(defaultPanelHeight('markdown')).toBe(6);
    expect(defaultPanelHeight('bar')).toBe(8);
    expect(defaultPanelHeight('pie')).toBe(8);
    expect(defaultPanelHeight('table')).toBe(10);
    expect(defaultPanelHeight('vertical-table')).toBe(10);
    expect(defaultPanelHeight('graph')).toBe(12);
  });

  it('falls back for unknown types', () => {
    expect(defaultPanelHeight('unknown')).toBe(8);
  });
});

describe('defaultMinHeight', () => {
  it('returns the per-type minimum height', () => {
    expect(defaultMinHeight('count')).toBe(3);
    expect(defaultMinHeight('table')).toBe(6);
    expect(defaultMinHeight('graph')).toBe(6);
    expect(defaultMinHeight('bar')).toBe(5);
  });

  it('falls back for unknown types', () => {
    expect(defaultMinHeight('unknown')).toBe(3);
  });
});

describe('defaultPanelWidth', () => {
  it('prefers w over size', () => {
    expect(defaultPanelWidth({ type: 'count', w: 4, size: 2 })).toBe(4);
  });

  it('falls back to size when w is unset', () => {
    expect(defaultPanelWidth({ type: 'count', size: 6 })).toBe(6);
  });

  it('uses 3 when both are unset', () => {
    expect(defaultPanelWidth({ type: 'count' })).toBe(3);
  });

  it('clamps to 1..cols', () => {
    expect(defaultPanelWidth({ type: 'count', w: 99 })).toBe(12);
    expect(defaultPanelWidth({ type: 'count', w: 0 })).toBe(1);
    expect(defaultPanelWidth({ type: 'count', w: -3 })).toBe(1);
  });
});

describe('deriveRowLayout', () => {
  it('packs panels left-to-right within a 12-col grid', () => {
    const panels: Panel[] = [
      { type: 'count', w: 3 },
      { type: 'count', w: 4 },
      { type: 'count', w: 5 }
    ];
    const layout = deriveRowLayout(panels);

    expect(layout).toHaveLength(3);
    expect(layout[0]).toMatchObject({ x: 0, y: 0, w: 3 });
    expect(layout[1]).toMatchObject({ x: 3, y: 0, w: 4 });
    expect(layout[2]).toMatchObject({ x: 7, y: 0, w: 5 });
  });

  it('wraps to a new row when cumulative width exceeds cols', () => {
    const panels: Panel[] = [
      { type: 'count', w: 8 },
      { type: 'count', w: 5 }
    ];
    const layout = deriveRowLayout(panels);

    expect(layout[0]).toMatchObject({ x: 0, y: 0 });
    expect(layout[1]).toMatchObject({ x: 0, y: 1 });
  });

  it('honors explicit x and y coordinates', () => {
    const panels: Panel[] = [
      { type: 'count', w: 3, x: 6, y: 0 },
      { type: 'count', w: 3, x: 9, y: 0 }
    ];
    const layout = deriveRowLayout(panels);

    expect(layout[0]).toMatchObject({ x: 6, y: 0, w: 3 });
    expect(layout[1]).toMatchObject({ x: 9, y: 0, w: 3 });
  });

  it('applies per-type default heights when h is unset', () => {
    const panels: Panel[] = [
      { type: 'count' },
      { type: 'table' },
      { type: 'graph' }
    ];
    const layout = deriveRowLayout(panels);

    expect(layout[0].h).toBe(4);
    expect(layout[1].h).toBe(10);
    expect(layout[2].h).toBe(12);
  });

  it('honors explicit h when set', () => {
    const panels: Panel[] = [{ type: 'count', h: 9 }];
    const layout = deriveRowLayout(panels);

    expect(layout[0].h).toBe(9);
  });

  it('honors explicit min_h when set', () => {
    const panels: Panel[] = [{ type: 'count', min_h: 7 }];
    const layout = deriveRowLayout(panels);

    expect(layout[0].minH).toBe(7);
  });

  it('falls back to size when w is missing (legacy panel)', () => {
    const panels: Panel[] = [{ type: 'count', size: 6 }];
    const layout = deriveRowLayout(panels);

    expect(layout[0].w).toBe(6);
  });
});

describe('buildResponsiveLayouts', () => {
  it('returns layouts for lg, md, sm, xs', () => {
    const panels: Panel[] = [{ type: 'count', w: 3 }];
    const layouts = buildResponsiveLayouts(panels);

    expect(Object.keys(layouts).sort()).toEqual(['lg', 'md', 'sm', 'xs']);
  });

  it('doubles widths at xs to mirror legacy mobile behavior', () => {
    const panels: Panel[] = [
      { type: 'count', w: 3 },
      { type: 'count', w: 4 }
    ];
    const layouts = buildResponsiveLayouts(panels);

    expect(layouts.lg[0].w).toBe(3);
    expect(layouts.xs[0].w).toBe(6);
    expect(layouts.xs[1].w).toBe(8);
  });

  it('caps doubled xs widths at the column count', () => {
    const panels: Panel[] = [{ type: 'count', w: 8 }];
    const layouts = buildResponsiveLayouts(panels);

    expect(layouts.xs[0].w).toBe(12);
  });

  it('repacks xs layouts so wide panels stack vertically', () => {
    const panels: Panel[] = [
      { type: 'count', w: 4 },
      { type: 'count', w: 4 },
      { type: 'count', w: 4 }
    ];
    const layouts = buildResponsiveLayouts(panels);

    // lg: three 4-wide panels fit in one row
    expect(layouts.lg.map((l) => l.y)).toEqual([0, 0, 0]);
    // xs: each becomes 8 wide → only one fits per row → stack
    expect(layouts.xs.map((l) => l.y)).toEqual([0, 1, 2]);
  });
});
