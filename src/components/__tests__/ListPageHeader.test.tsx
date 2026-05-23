import { cleanup, render, screen } from '@testing-library/react';
import ListPageHeader from 'src/components/ListPageHeader';

afterEach(cleanup);

describe('ListPageHeader', () => {
  it('renders a string title as an h1 and the action', () => {
    render(
      <ListPageHeader
        title="Toolsets"
        action={<button type="button">New toolset</button>}
      />,
    );

    const heading = screen.getByRole('heading', { level: 1, name: 'Toolsets' });
    expect(heading).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'New toolset' }),
    ).toBeInTheDocument();
  });

  it('renders a node title as-is', () => {
    render(<ListPageHeader title={<span>Custom title</span>} />);
    expect(screen.getByText('Custom title')).toBeInTheDocument();
    expect(screen.queryByRole('heading', { level: 1 })).not.toBeInTheDocument();
  });
});
