import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import DeleteIcon from '@mui/icons-material/Delete';
import EditIcon from '@mui/icons-material/Edit';
import RowMenu, { RowMenuAction } from 'src/components/RowMenu';

afterEach(cleanup);

function buildActions(
  overrides: Partial<RowMenuAction>[] = [],
): RowMenuAction[] {
  const base: RowMenuAction[] = [
    {
      key: 'edit',
      label: 'Edit',
      icon: <EditIcon fontSize="small" />,
      onClick: jest.fn(),
    },
    {
      key: 'delete',
      label: 'Delete',
      icon: <DeleteIcon fontSize="small" />,
      onClick: jest.fn(),
      destructive: true,
      dividerBefore: true,
    },
  ];
  return base.map((action, i) => ({ ...action, ...(overrides[i] ?? {}) }));
}

describe('RowMenu', () => {
  it('opens on trigger click and shows the actions', () => {
    render(<RowMenu actions={buildActions()} />);

    // Menu items are not mounted until the trigger is clicked.
    expect(screen.queryByText('Edit')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'More actions' }));

    expect(screen.getByText('Edit')).toBeInTheDocument();
    expect(screen.getByText('Delete')).toBeInTheDocument();
  });

  it('uses a custom trigger label', () => {
    render(<RowMenu actions={buildActions()} label="Row actions" />);
    expect(
      screen.getByRole('button', { name: 'Row actions' }),
    ).toBeInTheDocument();
  });

  it('fires an action handler and closes the menu', () => {
    const onEdit = jest.fn();
    render(<RowMenu actions={buildActions([{ onClick: onEdit }])} />);

    fireEvent.click(screen.getByRole('button', { name: 'More actions' }));
    fireEvent.click(screen.getByText('Edit'));

    expect(onEdit).toHaveBeenCalledTimes(1);
  });

  it('does not fire a disabled action', () => {
    const onEdit = jest.fn();
    render(
      <RowMenu actions={buildActions([{ onClick: onEdit, disabled: true }])} />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'More actions' }));
    const editItem = screen.getByText('Edit').closest('li');
    expect(editItem).toHaveAttribute('aria-disabled', 'true');

    fireEvent.click(screen.getByText('Edit'));
    expect(onEdit).not.toHaveBeenCalled();
  });
});
