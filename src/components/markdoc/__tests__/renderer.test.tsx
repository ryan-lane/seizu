import { render, screen, cleanup } from '@testing-library/react';
import { MarkdocRenderer } from '../renderer';

afterEach(cleanup);

describe('MarkdocRenderer', () => {
  it('substitutes variables from the variables prop', () => {
    render(<MarkdocRenderer source="Hello {% $name %}" variables={{ name: 'world' }} />);
    expect(screen.getByText(/Hello world/)).toBeInTheDocument();
  });

  it('treats undefined variables as empty strings', () => {
    const { container } = render(
      <MarkdocRenderer source="Hello {% $missing %}!" variables={{}} />
    );
    expect(container.textContent).toContain('Hello !');
  });

  it('demotes h1 in markdown source to h2 in output', () => {
    render(<MarkdocRenderer source={'# A heading'} />);
    const heading = screen.getByText('A heading');
    expect(heading.tagName).toBe('H2');
  });

  it('renders tables wrapped in a TableContainer', () => {
    const md = '| h1 | h2 |\n|----|----|\n| a  | b  |\n';
    const { container } = render(<MarkdocRenderer source={md} />);
    expect(container.querySelector('table')).not.toBeNull();
    expect(container.textContent).toContain('h1');
    expect(container.textContent).toContain('a');
  });

  it('applies the mui-markdown-ol class to ordered lists', () => {
    const { container } = render(<MarkdocRenderer source={'1. one\n2. two'} />);
    const ol = container.querySelector('ol');
    expect(ol).not.toBeNull();
    expect(ol?.className).toContain('mui-markdown-ol');
  });

  it('applies the mui-markdown-ul class to bullet lists', () => {
    const { container } = render(<MarkdocRenderer source={'- one\n- two'} />);
    const ul = container.querySelector('ul');
    expect(ul).not.toBeNull();
    expect(ul?.className).toContain('mui-markdown-ul');
  });
});
