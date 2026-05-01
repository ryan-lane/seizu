import { ReactNode, useEffect, useMemo, useState } from 'react';
import {
  Box,
  Paper,
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

export interface ListTableColumn<T> {
  key: string;
  label?: ReactNode;
  align?: ColumnAlign;
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
  const paginationEnabled = pagination && rows.length > rowsPerPage;

  useEffect(() => {
    const maxPage = Math.max(Math.ceil(rows.length / rowsPerPage) - 1, 0);
    if (page > maxPage) {
      setPage(maxPage);
    }
  }, [page, rows.length, rowsPerPage]);

  const visibleRows = useMemo(() => {
    if (!pagination) return rows;
    const start = page * rowsPerPage;
    return rows.slice(start, start + rowsPerPage);
  }, [page, pagination, rows, rowsPerPage]);

  return (
    <Paper variant="outlined">
      <TableContainer sx={{ overflowX: 'hidden' }}>
        <Table sx={{ tableLayout: 'fixed', width: '100%' }}>
          <TableHead>
            <TableRow>
              {columns.map((column) => (
                <TableCell
                  key={column.key}
                  align={column.align}
                  sx={mergeSx(hideBelowSx(column.hideBelow), column.cellSx, column.headerSx)}
                >
                  {column.label}
                </TableCell>
              ))}
            </TableRow>
          </TableHead>
          <TableBody>
            {rows.length === 0 && (
              <TableRow>
                <TableCell colSpan={columns.length}>
                  <Typography color="text.secondary" sx={{ py: 1 }}>
                    {emptyMessage}
                  </Typography>
                </TableCell>
              </TableRow>
            )}
            {visibleRows.map((row) => (
              <TableRow key={getRowKey(row)} hover>
                {columns.map((column) => (
                  <TableCell
                    key={column.key}
                    align={column.align}
                    sx={mergeSx(hideBelowSx(column.hideBelow), column.cellSx)}
                  >
                    {column.render(row)}
                  </TableCell>
                ))}
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
