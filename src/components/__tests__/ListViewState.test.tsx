import { cleanup, render, screen } from '@testing-library/react';
import ListViewState from 'src/components/ListViewState';

afterEach(cleanup);

describe('ListViewState', () => {
  it('shows a spinner while loading', () => {
    render(
      <ListViewState loading error={null}>
        <div>content</div>
      </ListViewState>,
    );
    expect(screen.getByRole('progressbar')).toBeInTheDocument();
    expect(screen.queryByText('content')).not.toBeInTheDocument();
  });

  it('shows the error message on error', () => {
    render(
      <ListViewState
        loading={false}
        error={new Error('boom')}
        errorMessage="Failed to load widgets"
      >
        <div>content</div>
      </ListViewState>,
    );
    expect(screen.getByText('Failed to load widgets')).toBeInTheDocument();
    expect(screen.queryByText('content')).not.toBeInTheDocument();
  });

  it('renders children when not loading and no error', () => {
    render(
      <ListViewState loading={false} error={null}>
        <div>content</div>
      </ListViewState>,
    );
    expect(screen.getByText('content')).toBeInTheDocument();
  });
});
