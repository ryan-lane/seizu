import { isValidElement, type MouseEvent as ReactMouseEvent, ReactNode, useEffect, useMemo, useRef, useState } from 'react';
import {
  Box,
  Paper,
  Tooltip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TablePagination,
  TableRow,
  Typography
} from '@mui/material';
import type { Breakpoint, SxProps, Theme } from '@mui/material/styles';

type ColumnAlign = 'inherit' | 'left' | 'center' | 'right' | 'justify';
type ColumnWidth = number | string;

export interface ListTableColumn<T> {
  key: string;
  label?: ReactNode;
  align?: ColumnAlign;
  width?: ColumnWidth;
  minWidth?: number;
  resizable?: boolean;
  cellSx?: SxProps<Theme>;
  headerSx?: SxProps<Theme>;
  hideBelow?: Exclude<Breakpoint, 'xs'>;
  render: (row: T) => ReactNode;
}

interface ListTableProps<T> {
  rows: T[];
  columns: ListTableColumn<T>[];
  getRowKey: (row: T) => string | number;
  emptyMessage: ReactNode;
  pagination?: boolean;
  initialRowsPerPage?: number;
  rowsPerPageOptions?: number[];
}

function hideBelowSx(hideBelow: ListTableColumn<unknown>['hideBelow']): SxProps<Theme> {
  if (!hideBelow) return {};
  return {
    display: {
      xs: 'none',
      [hideBelow]: 'table-cell'
    }
  };
}

function mergeSx(...items: Array<SxProps<Theme> | undefined>): SxProps<Theme> {
  return items.filter(Boolean) as SxProps<Theme>;
}

function extractWidthSx(sx: SxProps<Theme> | undefined): ColumnWidth | undefined {
  if (!sx || Array.isArray(sx) || typeof sx === 'function') return undefined;
  const width = (sx as Record<string, unknown>).width;
  return typeof width === 'number' || typeof width === 'string' ? width : undefined;
}

function widthToCss(width: ColumnWidth): string {
  return typeof width === 'number' ? `${width}px` : width;
}

function getNodeTextContent(node: ReactNode): string {
  if (node === null || node === undefined || typeof node === 'boolean') return '';
  if (typeof node === 'string' || typeof node === 'number') return String(node);
  if (Array.isArray(node)) {
    return node.map((child) => getNodeTextContent(child)).filter(Boolean).join(' ');
  }
  if (isValidElement(node)) {
    const props = node.props as {
      children?: ReactNode;
      label?: ReactNode;
      title?: ReactNode;
      ['aria-label']?: ReactNode;
    };
    return [
      getNodeTextContent(props.label),
      getNodeTextContent(props.title),
      getNodeTextContent(props['aria-label']),
      getNodeTextContent(props.children)
    ].filter(Boolean).join(' ');
  }
  return '';
}

function isResizingDisabled(column: ListTableColumn<unknown>): boolean {
  if (column.resizable !== undefined) return !column.resizable;
  return column.key === 'actions' || column.key === 'row_actions';
}

export const listTableActionColumnSx = {
  width: 48,
  minWidth: 48,
  pr: 1
} as const;

export const listTablePrimaryCellSx = {
  minWidth: 0
} as const;

export const listTableSecondaryCellSx = {
  color: 'text.secondary'
} as const;

export const listTableMonoCellSx = {
  color: 'text.secondary',
  fontFamily: 'monospace'
} as const;

export const listTableTruncateSx = {
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
  minWidth: 0
} as const;

const listTableCellContentSx = {
  ...listTableTruncateSx,
  display: 'block',
  maxWidth: '100%'
} as const;

const listTableHeaderContentSx = {
  ...listTableCellContentSx,
  display: 'flex',
  alignItems: 'center',
  gap: 0.5
} as const;

function TableCellHoverTooltip({
  content,
  children
}: {
  content: ReactNode;
  children: ReactNode;
}) {
  const tooltip = getNodeTextContent(content);
  if (!tooltip) return <>{children}</>;

  return (
    <Tooltip title={tooltip} placement="top" arrow disableInteractive>
      <Box component="span" sx={{ display: 'block', minWidth: 0 }}>
        {children}
      </Box>
    </Tooltip>
  );
}

export default function ListTable<T>({
  rows,
  columns,
  getRowKey,
  emptyMessage,
  pagination = true,
  initialRowsPerPage = 10,
  rowsPerPageOptions = [10, 25, 50]
}: ListTableProps<T>) {
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(initialRowsPerPage);
  const [columnWidths, setColumnWidths] = useState<Record<string, number>>({});
  const paginationEnabled = pagination && rows.length > rowsPerPage;
  const headerCellRefs = useRef<Record<string, HTMLElement | null>>({});
  const resizeDragRef = useRef<{
    targetIndex: number;
    startX: number;
    baseWidths: Record<string, number>;
  } | null>(null);
  const resizeListenersRef = useRef<{
    handleMouseMove: (event: MouseEvent) => void;
    handleMouseUp: () => void;
  } | null>(null);

  useEffect(() => {
    const maxPage = Math.max(Math.ceil(rows.length / rowsPerPage) - 1, 0);
    if (page > maxPage) {
      setPage(maxPage);
    }
  }, [page, rows.length, rowsPerPage]);

  useEffect(() => () => {
    if (resizeListenersRef.current) {
      const { handleMouseMove, handleMouseUp } = resizeListenersRef.current;
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
      resizeListenersRef.current = null;
    }
    resizeDragRef.current = null;
  }, []);

  const visibleRows = useMemo(() => {
    if (!pagination) return rows;
    const start = page * rowsPerPage;
    return rows.slice(start, start + rowsPerPage);
  }, [page, pagination, rows, rowsPerPage]);

  const getColumnMinWidth = (column: ListTableColumn<T>): number => Math.max(48, column.minWidth ?? 48);

  const getColumnWidth = (column: ListTableColumn<T>): number => {
    const explicitWidth = columnWidths[column.key];
    if (explicitWidth !== undefined) return explicitWidth;

    const measuredWidth = headerCellRefs.current[column.key]?.getBoundingClientRect().width ?? 0;
    if (measuredWidth > 0) return Math.round(measuredWidth);

    if (typeof column.width === 'number') return column.width;
    if (typeof column.width === 'string' && column.width.trim().endsWith('px')) {
      const parsed = Number.parseFloat(column.width);
      if (Number.isFinite(parsed)) return parsed;
    }

    return 0;
  };

  const snapshotColumnWidths = () => columns.reduce<Record<string, number>>((acc, column) => {
    const width = getColumnWidth(column);
    if (width > 0) {
      acc[column.key] = width;
    }
    return acc;
  }, {});

  const redistributeWidths = (
    baseWidths: Record<string, number>,
    targetIndex: number,
    delta: number
  ): Record<string, number> => {
    const nextWidths = { ...baseWidths };
    const targetColumn = columns[targetIndex];
    const targetMinWidth = getColumnMinWidth(targetColumn);
    const currentTargetWidth = baseWidths[targetColumn.key] ?? targetMinWidth;
    let targetWidth = Math.max(targetMinWidth, currentTargetWidth + delta);
    let appliedDelta = targetWidth - currentTargetWidth;

    const absorbShrink = (orderedColumns: ListTableColumn<T>[], amount: number): number => {
      let remaining = amount;
      for (const column of orderedColumns) {
        if (remaining <= 0) break;
        const currentWidth = nextWidths[column.key] ?? baseWidths[column.key] ?? getColumnMinWidth(column);
        const minWidth = getColumnMinWidth(column);
        const reducible = Math.max(0, currentWidth - minWidth);
        if (reducible === 0) continue;
        const reduction = Math.min(remaining, reducible);
        nextWidths[column.key] = currentWidth - reduction;
        remaining -= reduction;
      }
      return remaining;
    };

    const absorbGrowth = (orderedColumns: ListTableColumn<T>[], amount: number): number => {
      let remaining = amount;
      for (const column of orderedColumns) {
        if (remaining <= 0) break;
        const currentWidth = nextWidths[column.key] ?? baseWidths[column.key] ?? getColumnMinWidth(column);
        nextWidths[column.key] = currentWidth + remaining;
        remaining = 0;
      }
      return remaining;
    };

    const rightColumns = columns.slice(targetIndex + 1);
    const leftColumns = columns.slice(0, targetIndex).reverse();

    if (appliedDelta > 0) {
      const remainingAfterRight = absorbShrink(rightColumns, appliedDelta);
      const remainingAfterLeft = remainingAfterRight > 0
        ? absorbShrink(leftColumns, remainingAfterRight)
        : 0;
      appliedDelta -= remainingAfterLeft;
      targetWidth = currentTargetWidth + appliedDelta;
    } else if (appliedDelta < 0) {
      const growthAmount = -appliedDelta;
      const receiverColumns = rightColumns.length > 0 ? [rightColumns[0]] : leftColumns.slice(0, 1);
      const remainingAfterGrowth = absorbGrowth(receiverColumns, growthAmount);
      if (remainingAfterGrowth > 0) {
        targetWidth = currentTargetWidth;
      }
    }

    nextWidths[targetColumn.key] = targetWidth;
    return nextWidths;
  };

  const startResize = (column: ListTableColumn<T>, event: ReactMouseEvent<HTMLSpanElement>) => {
    if (isResizingDisabled(column)) return;
    if (resizeDragRef.current) return;
    const targetIndex = columns.findIndex((candidate) => candidate.key === column.key);
    if (targetIndex < 0) return;
    const baseWidths = snapshotColumnWidths();
    resizeDragRef.current = {
      targetIndex,
      startX: event.clientX,
      baseWidths
    };

    const handleMouseMove = (moveEvent: MouseEvent) => {
      const drag = resizeDragRef.current;
      if (!drag) return;
      const delta = moveEvent.clientX - drag.startX;
      setColumnWidths(redistributeWidths(drag.baseWidths, drag.targetIndex, delta));
    };

    const handleMouseUp = () => {
      resizeDragRef.current = null;
      resizeListenersRef.current = null;
      document.body.style.userSelect = '';
      document.body.style.cursor = '';
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };

    document.body.style.userSelect = 'none';
    document.body.style.cursor = 'col-resize';
    resizeListenersRef.current = { handleMouseMove, handleMouseUp };
    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    event.preventDefault();
    event.stopPropagation();
  };

  const getWidthStyle = (column: ListTableColumn<T>): SxProps<Theme> => {
    const width = columnWidths[column.key] ?? column.width ?? extractWidthSx(column.cellSx) ?? extractWidthSx(column.headerSx);
    if (width === undefined) return {};
    return {
      width: widthToCss(width),
      minWidth: widthToCss(getColumnMinWidth(column))
    };
  };

  return (
    <Paper variant="outlined">
      <TableContainer sx={{ overflowX: 'auto' }}>
        <Table sx={{ tableLayout: 'fixed', width: '100%' }}>
          <TableHead>
            <TableRow>
              {columns.map((column) => (
                <TableCell
                  key={column.key}
                  align={column.align}
                  ref={(node) => {
                    headerCellRefs.current[column.key] = node as HTMLElement | null;
                  }}
                  sx={mergeSx(
                    hideBelowSx(column.hideBelow),
                    column.cellSx,
                    column.headerSx,
                    getWidthStyle(column),
                    {
                      position: 'relative',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                      '&:hover .list-table-resize-handle': {
                        opacity: 1
                      }
                    }
                  )}
                >
                  <Box sx={{ ...listTableHeaderContentSx, pr: 1.5 }}>
                    <TableCellHoverTooltip content={column.label}>
                      <Box component="span" sx={{ ...listTableCellContentSx, flex: '1 1 auto' }}>
                        {column.label}
                      </Box>
                    </TableCellHoverTooltip>
                    {!isResizingDisabled(column) && (
                      <Box
                        component="span"
                        onMouseDown={(event) => startResize(column, event)}
                        className="list-table-resize-handle"
                        sx={{
                          position: 'absolute',
                          top: 0,
                          right: 0,
                          bottom: 0,
                          width: 6,
                          cursor: 'col-resize',
                          opacity: 0,
                          transition: 'opacity 120ms ease',
                          '&::after': {
                            content: '""',
                            position: 'absolute',
                            top: 0,
                            bottom: 0,
                            left: '50%',
                            width: 1,
                            transform: 'translateX(-50%)',
                            bgcolor: 'divider'
                          },
                          '&:hover::after': {
                            bgcolor: 'primary.main'
                          },
                          '&:hover': {
                            opacity: 1
                          }
                        }}
                      />
                    )}
                  </Box>
                </TableCell>
              ))}
            </TableRow>
          </TableHead>
          <TableBody>
            {rows.length === 0 && (
              <TableRow>
                <TableCell colSpan={columns.length}>
                  <Box component="div" sx={listTableCellContentSx}>
                    <Typography color="text.secondary" sx={{ py: 1 }}>
                      {emptyMessage}
                    </Typography>
                  </Box>
                </TableCell>
              </TableRow>
            )}
            {visibleRows.map((row) => (
              <TableRow key={getRowKey(row)} hover>
                {columns.map((column) => {
                  const cellContent = column.render(row);
                  return (
                    <TableCell
                      key={column.key}
                      align={column.align}
                      sx={mergeSx(
                        hideBelowSx(column.hideBelow),
                        column.cellSx,
                        getWidthStyle(column),
                        {
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap'
                        }
                      )}
                    >
                      <TableCellHoverTooltip content={cellContent}>
                        <Box component="div" sx={listTableCellContentSx}>
                          {cellContent}
                        </Box>
                      </TableCellHoverTooltip>
                    </TableCell>
                  );
                })}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
      {paginationEnabled && (
        <Box sx={{ borderTop: 1, borderColor: 'divider' }}>
          <TablePagination
            component="div"
            count={rows.length}
            page={page}
            rowsPerPage={rowsPerPage}
            rowsPerPageOptions={rowsPerPageOptions}
            onPageChange={(_event, nextPage) => setPage(nextPage)}
            onRowsPerPageChange={(event) => {
              setRowsPerPage(parseInt(event.target.value, 10));
              setPage(0);
            }}
          />
        </Box>
      )}
    </Paper>
  );
}
