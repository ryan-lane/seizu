import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import MarkdownPanelEditor from '../MarkdownPanelEditor';

afterEach(cleanup);

describe('MarkdownPanelEditor', () => {
  it('renders the mode toggle with WYSIWYG selected by default', () => {
    render(<MarkdownPanelEditor value="" onChange={() => {}} />);
    const wysiwyg = screen.getByRole('button', { name: /WYSIWYG editor/i });
    const source = screen.getByRole('button', { name: /Markdown source/i });
    expect(wysiwyg).toBeInTheDocument();
    expect(source).toBeInTheDocument();
    expect(wysiwyg).toHaveAttribute('aria-pressed', 'true');
    expect(source).toHaveAttribute('aria-pressed', 'false');
  });

  it('renders toolbar buttons in WYSIWYG mode', () => {
    render(<MarkdownPanelEditor value="" onChange={() => {}} />);
    expect(screen.getByRole('button', { name: 'Bold' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Italic' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Strikethrough' })).toBeInTheDocument();
    expect(screen.getByRole('combobox', { name: 'Heading level' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Bullet list' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Ordered list' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Task list' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Blockquote' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Inline code' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Code block' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Link' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Remove link' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Table' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Horizontal rule' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Undo' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Redo' })).toBeInTheDocument();
  });

  it('opens a menu of table actions when the Table button is clicked', () => {
    render(<MarkdownPanelEditor value="" onChange={() => {}} />);
    fireEvent.click(screen.getByRole('button', { name: 'Table' }));
    expect(screen.getByRole('menuitem', { name: 'Insert table' })).toBeInTheDocument();
    expect(screen.getByRole('menuitem', { name: 'Add row below' })).toBeInTheDocument();
    expect(screen.getByRole('menuitem', { name: 'Delete row' })).toBeInTheDocument();
    expect(screen.getByRole('menuitem', { name: 'Add column after' })).toBeInTheDocument();
    expect(screen.getByRole('menuitem', { name: 'Delete column' })).toBeInTheDocument();
    expect(screen.getByRole('menuitem', { name: 'Delete table' })).toBeInTheDocument();
  });

  it('disables cell manipulation menu items when not inside a table', () => {
    render(<MarkdownPanelEditor value="" onChange={() => {}} />);
    fireEvent.click(screen.getByRole('button', { name: 'Table' }));
    expect(screen.getByRole('menuitem', { name: 'Insert table' })).not.toHaveAttribute(
      'aria-disabled',
      'true'
    );
    expect(screen.getByRole('menuitem', { name: 'Delete row' })).toHaveAttribute(
      'aria-disabled',
      'true'
    );
    expect(screen.getByRole('menuitem', { name: 'Delete column' })).toHaveAttribute(
      'aria-disabled',
      'true'
    );
    expect(screen.getByRole('menuitem', { name: 'Delete table' })).toHaveAttribute(
      'aria-disabled',
      'true'
    );
  });

  it('switches to source mode and shows the markdown TextField populated with value', () => {
    render(<MarkdownPanelEditor value={'# Title\n\nHello'} onChange={() => {}} />);
    fireEvent.click(screen.getByRole('button', { name: /Markdown source/i }));
    const field = screen.getByLabelText('Markdown content');
    expect(field).toBeInTheDocument();
    expect(field).toHaveValue('# Title\n\nHello');
  });

  it('calls onChange with the string value when editing in source mode', () => {
    const onChange = jest.fn();
    render(<MarkdownPanelEditor value="" onChange={onChange} />);
    fireEvent.click(screen.getByRole('button', { name: /Markdown source/i }));
    const field = screen.getByLabelText('Markdown content');
    fireEvent.change(field, { target: { value: '## Hi' } });
    expect(onChange).toHaveBeenLastCalledWith('## Hi');
  });

  it('calls onChange with undefined when source field is cleared', () => {
    const onChange = jest.fn();
    render(<MarkdownPanelEditor value="existing" onChange={onChange} />);
    fireEvent.click(screen.getByRole('button', { name: /Markdown source/i }));
    const field = screen.getByLabelText('Markdown content');
    fireEvent.change(field, { target: { value: '' } });
    expect(onChange).toHaveBeenLastCalledWith(undefined);
  });

  it('hides the toolbar when in source mode', () => {
    render(<MarkdownPanelEditor value="" onChange={() => {}} />);
    fireEvent.click(screen.getByRole('button', { name: /Markdown source/i }));
    expect(screen.queryByRole('button', { name: 'Bold' })).not.toBeInTheDocument();
  });

  it('opens the link dialog when the link button is clicked', () => {
    render(<MarkdownPanelEditor value="" onChange={() => {}} />);
    fireEvent.click(screen.getByRole('button', { name: 'Link' }));
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByLabelText('URL')).toBeInTheDocument();
  });

});
