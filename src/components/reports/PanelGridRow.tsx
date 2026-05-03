import { ReactNode, useMemo } from 'react';
import {
  ResponsiveGridLayout,
  useContainerWidth,
  type Layout,
  type ResponsiveLayouts
} from 'react-grid-layout';
import { Panel } from 'src/config.context';
import {
  buildResponsiveLayouts,
  RESPONSIVE_BREAKPOINTS,
  RESPONSIVE_COLS,
  type ResponsiveBreakpoint
} from 'src/components/reports/panelLayout';

const ROW_HEIGHT = 48;
const MARGIN: [number, number] = [12, 12];
const CONTAINER_PADDING: [number, number] = [0, 0];

const DRAG_CANCEL_SELECTOR =
  '.MuiIconButton-root, .MuiTextField-root, .MuiButton-root, .MuiTabs-root, .MuiSelect-select, button, input, textarea';

export interface PanelGridRowProps {
  panels: Panel[];
  renderPanel: (panel: Panel, index: number) => ReactNode;
  isEditing?: boolean;
  onLayoutChange?: (
    layoutsByBreakpoint: ResponsiveLayouts<ResponsiveBreakpoint>
  ) => void;
  className?: string;
}

function panelKey(_panel: Panel, idx: number): string {
  return `${idx}`;
}

function PanelGridRow({
  panels,
  renderPanel,
  isEditing = false,
  onLayoutChange,
  className
}: PanelGridRowProps) {
  const layouts = useMemo(() => buildResponsiveLayouts(panels), [panels]);
  const { width, containerRef, mounted } = useContainerWidth();

  const items = panels.map((panel, idx) => (
    <div
      key={panelKey(panel, idx)}
      style={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}
    >
      {renderPanel(panel, idx)}
    </div>
  ));

  return (
    <div ref={containerRef} className={`report-row${className ? ` ${className}` : ''}`}>
      {mounted && (
        <ResponsiveGridLayout<ResponsiveBreakpoint>
          width={width}
          layouts={layouts}
          breakpoints={RESPONSIVE_BREAKPOINTS}
          cols={RESPONSIVE_COLS}
          rowHeight={ROW_HEIGHT}
          margin={MARGIN}
          containerPadding={CONTAINER_PADDING}
          dragConfig={{
            enabled: isEditing,
            cancel: isEditing ? DRAG_CANCEL_SELECTOR : undefined
          }}
          resizeConfig={{ enabled: isEditing }}
          onLayoutChange={(_current: Layout, all: ResponsiveLayouts<ResponsiveBreakpoint>) =>
            onLayoutChange?.(all)
          }
        >
          {items}
        </ResponsiveGridLayout>
      )}
    </div>
  );
}

export default PanelGridRow;
