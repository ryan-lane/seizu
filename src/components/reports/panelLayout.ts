import { Panel } from 'src/config.context';

export interface LayoutCoords {
  i: string;
  x: number;
  y: number;
  w: number;
  h: number;
  minH: number;
  minW: number;
}

export type ResponsiveBreakpoint = 'lg' | 'md' | 'sm' | 'xs';

export const RESPONSIVE_BREAKPOINTS: Record<ResponsiveBreakpoint, number> = {
  lg: 1200,
  md: 900,
  sm: 600,
  xs: 0,
};

export const RESPONSIVE_COLS: Record<ResponsiveBreakpoint, number> = {
  lg: 12,
  md: 12,
  sm: 12,
  xs: 12,
};

const PANEL_HEIGHT_DEFAULTS: Record<string, number> = {
  count: 4,
  progress: 4,
  markdown: 6,
  bar: 8,
  pie: 8,
  table: 10,
  'vertical-table': 10,
  graph: 12,
};

const PANEL_MIN_HEIGHT_DEFAULTS: Record<string, number> = {
  count: 3,
  progress: 3,
  markdown: 3,
  bar: 5,
  pie: 5,
  table: 6,
  'vertical-table': 6,
  graph: 6,
};

const FALLBACK_HEIGHT = 8;
const FALLBACK_MIN_HEIGHT = 3;
const FALLBACK_WIDTH = 3;
const MAX_COLS = 12;

export function defaultPanelHeight(panelType: string): number {
  return PANEL_HEIGHT_DEFAULTS[panelType] ?? FALLBACK_HEIGHT;
}

export function defaultMinHeight(panelType: string): number {
  return PANEL_MIN_HEIGHT_DEFAULTS[panelType] ?? FALLBACK_MIN_HEIGHT;
}

function clampWidth(value: number, cols: number): number {
  if (Number.isNaN(value)) return FALLBACK_WIDTH;
  return Math.max(1, Math.min(cols, Math.trunc(value)));
}

export function defaultPanelWidth(panel: Panel, cols: number = MAX_COLS): number {
  const raw = panel.w ?? panel.size ?? FALLBACK_WIDTH;
  return clampWidth(raw, cols);
}

export function defaultPanelHeightFor(panel: Panel): number {
  if (panel.h != null) return Math.max(1, Math.trunc(panel.h));
  return defaultPanelHeight(panel.type);
}

function panelKey(panel: Panel, idx: number): string {
  return `${idx}`;
}

/**
 * Pack panels left-to-right, wrapping when their cumulative width exceeds the
 * grid column count. Panels with explicit ``x`` and ``y`` keep their position.
 *
 * Auto-packed panels share the topmost free row alongside other auto-packed
 * panels; explicit-coordinate panels are not re-flowed.
 */
export function deriveRowLayout(panels: Panel[], cols: number = MAX_COLS): LayoutCoords[] {
  const result: LayoutCoords[] = [];
  let cursorX = 0;
  let cursorY = 0;

  panels.forEach((panel, idx) => {
    const w = defaultPanelWidth(panel, cols);
    const h = defaultPanelHeightFor(panel);
    const minH = panel.min_h ?? defaultMinHeight(panel.type);

    let x: number;
    let y: number;
    if (panel.x != null && panel.y != null) {
      x = Math.max(0, Math.min(cols - w, Math.trunc(panel.x)));
      y = Math.max(0, Math.trunc(panel.y));
    } else {
      if (cursorX + w > cols) {
        cursorX = 0;
        cursorY += 1;
      }
      x = cursorX;
      y = cursorY;
      cursorX += w;
    }

    result.push({
      i: panelKey(panel, idx),
      x,
      y,
      w,
      h,
      minH,
      minW: 1,
    });
  });

  return result;
}

/**
 * Build a layout map for every responsive breakpoint. At ``xs`` (mobile),
 * panel widths are doubled (capped to the column count) and panels stack
 * vertically — matching the legacy ``xsSize = item.size * 2`` behavior in
 * ``ReportView.tsx``.
 */
export function buildResponsiveLayouts(
  panels: Panel[],
): Record<ResponsiveBreakpoint, LayoutCoords[]> {
  const wide = deriveRowLayout(panels, MAX_COLS);

  const xsPanels: Panel[] = panels.map((panel) => {
    const baseW = defaultPanelWidth(panel, MAX_COLS);
    const doubled = Math.min(MAX_COLS, baseW * 2);
    return { ...panel, w: doubled, x: undefined, y: undefined };
  });
  const xs = deriveRowLayout(xsPanels, MAX_COLS);

  return {
    lg: wide,
    md: wide,
    sm: wide,
    xs,
  };
}
