import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import ConfirmDeleteDialog from 'src/components/ConfirmDeleteDialog';

afterEach(cleanup);

describe('ConfirmDeleteDialog', () => {
  it('renders title and body and fires confirm/cancel', () => {
    const onConfirm = jest.fn();
    const onClose = jest.fn();
    render(
      <ConfirmDeleteDialog
        open
        title="Delete widget?"
        onConfirm={onConfirm}
        onClose={onClose}
      >
        Permanently delete <strong>My widget</strong>?
      </ConfirmDeleteDialog>,
    );

    expect(screen.getByText('Delete widget?')).toBeInTheDocument();
    expect(screen.getByText('My widget')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Delete' }));
    expect(onConfirm).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('disables actions and shows a spinner while deleting', () => {
    render(
      <ConfirmDeleteDialog
        open
        deleting
        onConfirm={jest.fn()}
        onClose={jest.fn()}
      >
        body
      </ConfirmDeleteDialog>,
    );
    expect(screen.getByRole('progressbar')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Cancel' })).toBeDisabled();
  });

  it('shows an error alert when error is set', () => {
    render(
      <ConfirmDeleteDialog
        open
        error="Could not delete"
        onConfirm={jest.fn()}
        onClose={jest.fn()}
      >
        body
      </ConfirmDeleteDialog>,
    );
    expect(screen.getByText('Could not delete')).toBeInTheDocument();
  });
});
