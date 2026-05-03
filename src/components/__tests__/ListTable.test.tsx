import { fireEvent, render, screen } from '@testing-library/react';
import ListTable, { ListTableColumn } from 'src/components/ListTable';

interface Row {
  id: string;
  name: string;
}

const rows: Row[] = Array.from({ length: 12 }, (_, index) => ({
  id: `row-${index + 1}`,
  name: `Row ${index + 1}`,
}));

const columns: ListTableColumn<Row>[] = [
  {
    key: 'name',
    label: 'Name',
    render: (row) => row.name,
  },
];

describe('ListTable', () => {
  it('paginates rows on the client', () => {
    render(
      <ListTable
        rows={rows}
        columns={columns}
        getRowKey={(row) => row.id}
        emptyMessage="No rows."
      />
    );

    expect(screen.getByText('Row 1')).toBeInTheDocument();
    expect(screen.queryByText('Row 11')).not.toBeInTheDocument();

    fireEvent.click(screen.getByLabelText('Go to next page'));

    expect(screen.getByText('Row 11')).toBeInTheDocument();
    expect(screen.queryByText('Row 1')).not.toBeInTheDocument();
  });

  it('keeps pagination controls visible when rows per page exceeds the row count', () => {
    render(
      <ListTable
        rows={rows}
        columns={columns}
        getRowKey={(row) => row.id}
        emptyMessage="No rows."
      />
    );

    fireEvent.click(screen.getByLabelText('Go to next page'));
    fireEvent.mouseDown(screen.getByRole('combobox'));
    fireEvent.click(screen.getByRole('option', { name: '25' }));

    expect(screen.getByRole('combobox')).toBeInTheDocument();
    expect(screen.getByText('Row 1')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Go to next page' })).toBeDisabled();
  });

  it('shows an empty row when there are no rows', () => {
    render(
      <ListTable
        rows={[]}
        columns={columns}
        getRowKey={(row) => row.id}
        emptyMessage="No rows."
      />
    );

    expect(screen.getByText('No rows.')).toBeInTheDocument();
  });
});
