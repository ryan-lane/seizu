import MarkdownEditor from 'src/components/MarkdownEditor';
import type { MarkdocVariableOption } from 'src/components/MarkdownEditor';

interface MarkdownPanelEditorProps {
  value: string | undefined;
  onChange: (value: string | undefined) => void;
  availableVariables?: MarkdocVariableOption[];
}

function MarkdownPanelEditor({ value, onChange, availableVariables }: MarkdownPanelEditorProps) {
  return <MarkdownEditor value={value} onChange={onChange} availableVariables={availableVariables} />;
}

export default MarkdownPanelEditor;
