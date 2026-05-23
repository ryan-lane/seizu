import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import DetailDialog, {
  DetailSection,
  DetailCodeBlock,
} from 'src/components/DetailDialog';

afterEach(cleanup);

describe('DetailDialog', () => {
  it('renders title, secondary label, sections and code block', () => {
    render(
      <DetailDialog open onClose={jest.fn()} title="My tool" secondary="v3">
        <DetailSection title="Cypher">
          <DetailCodeBlock>MATCH (n) RETURN n</DetailCodeBlock>
        </DetailSection>
      </DetailDialog>,
    );

    expect(screen.getByText('My tool')).toBeInTheDocument();
    expect(screen.getByText('v3')).toBeInTheDocument();
    expect(screen.getByText('Cypher')).toBeInTheDocument();
    expect(screen.getByText('MATCH (n) RETURN n')).toBeInTheDocument();
  });

  it('fires onClose from the close button', () => {
    const onClose = jest.fn();
    render(
      <DetailDialog open onClose={onClose} title="My tool">
        body
      </DetailDialog>,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Close' }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
