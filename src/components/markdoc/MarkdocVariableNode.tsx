import { Node, mergeAttributes } from '@tiptap/core';
import { NodeViewWrapper, ReactNodeViewRenderer } from '@tiptap/react';
import type { NodeViewProps } from '@tiptap/react';
import { Chip } from '@mui/material';

export const MARKDOC_VAR_RE = /\{%\s*\$([a-z][a-z0-9_]*)\s*%\}/g;

export function expandMarkdocVariables(markdown: string): string {
  return markdown.replace(
    MARKDOC_VAR_RE,
    (_match, name) => `<span data-markdoc-var="${name}"></span>`
  );
}

declare module '@tiptap/core' {
  interface Commands<ReturnType> {
    markdocVariable: {
      insertMarkdocVariable: (attrs: { name: string }) => ReturnType;
    };
  }
}

function MarkdocVariableChip({ node }: NodeViewProps) {
  const name = (node.attrs.name as string | undefined) ?? '';
  return (
    <NodeViewWrapper as="span" style={{ display: 'inline-block', verticalAlign: 'baseline' }}>
      <Chip
        size="small"
        label={`$${name}`}
        sx={{
          fontFamily: 'monospace',
          height: 22,
          fontSize: '0.78rem',
          bgcolor: 'action.hover',
          color: 'primary.main',
          border: '1px solid',
          borderColor: 'divider',
          '& .MuiChip-label': { px: 0.75 },
        }}
      />
    </NodeViewWrapper>
  );
}

export const MarkdocVariable = Node.create({
  name: 'markdocVariable',
  group: 'inline',
  inline: true,
  atom: true,
  selectable: true,
  draggable: false,

  addAttributes() {
    return {
      name: {
        default: '',
        parseHTML: (element) => element.getAttribute('data-markdoc-var') ?? '',
        renderHTML: (attrs) => ({ 'data-markdoc-var': attrs.name as string }),
      },
    };
  },

  parseHTML() {
    return [{ tag: 'span[data-markdoc-var]' }];
  },

  renderHTML({ HTMLAttributes, node }) {
    const name = (node.attrs.name as string | undefined) ?? '';
    return ['span', mergeAttributes(HTMLAttributes, { 'data-markdoc-var': name }), `{%$${name}%}`];
  },

  addNodeView() {
    return ReactNodeViewRenderer(MarkdocVariableChip);
  },

  addCommands() {
    return {
      insertMarkdocVariable:
        (attrs) =>
        ({ commands }) =>
          commands.insertContent({ type: this.name, attrs }),
    };
  },

  addStorage() {
    return {
      markdown: {
        serialize(state: { write: (s: string) => void }, node: { attrs: { name: string } }) {
          // Compact form (no spaces) is required so markdown-it can parse links
          // like `[label](https://example.com/{%$foo%})`. The renderer's regex
          // accepts both `{%$foo%}` and `{% $foo %}` on input.
          state.write(`{%$${node.attrs.name}%}`);
        },
        parse: {},
      },
    };
  },
});

export default MarkdocVariable;
