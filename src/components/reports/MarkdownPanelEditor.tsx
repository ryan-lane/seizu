import MarkdownEditor from 'src/components/MarkdownEditor';

interface MarkdownPanelEditorProps {
  value: string | undefined;
  onChange: (value: string | undefined) => void;
}

function MarkdownPanelEditor({ value, onChange }: MarkdownPanelEditorProps) {
  return <MarkdownEditor value={value} onChange={onChange} />;
}

export default MarkdownPanelEditor;
