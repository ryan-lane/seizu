import { useEffect, useRef, useState } from 'react';
import {
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  IconButton,
  Menu,
  MenuItem,
  Stack,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Tooltip
} from '@mui/material';
import CodeIcon from '@mui/icons-material/Code';
import DataObjectIcon from '@mui/icons-material/DataObject';
import FormatBoldIcon from '@mui/icons-material/FormatBold';
import FormatItalicIcon from '@mui/icons-material/FormatItalic';
import FormatListBulletedIcon from '@mui/icons-material/FormatListBulleted';
import FormatListNumberedIcon from '@mui/icons-material/FormatListNumbered';
import FormatQuoteIcon from '@mui/icons-material/FormatQuote';
import LinkIcon from '@mui/icons-material/Link';
import LinkOffIcon from '@mui/icons-material/LinkOff';
import RedoIcon from '@mui/icons-material/Redo';
import TableChartIcon from '@mui/icons-material/TableChart';
import UndoIcon from '@mui/icons-material/Undo';
import { EditorContent, useEditor } from '@tiptap/react';
import type { Editor } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import { Table } from '@tiptap/extension-table';
import { TableCell } from '@tiptap/extension-table-cell';
import { TableHeader } from '@tiptap/extension-table-header';
import { TableRow } from '@tiptap/extension-table-row';
import { Markdown } from 'tiptap-markdown';
import type { MarkdownStorage } from 'tiptap-markdown';

type Mode = 'wysiwyg' | 'source';

interface MarkdownPanelEditorProps {
  value: string | undefined;
  onChange: (value: string | undefined) => void;
}

function getMarkdown(editor: Editor): string {
  const storage = (editor.storage as unknown as Record<string, unknown>).markdown as
    | MarkdownStorage
    | undefined;
  return storage?.getMarkdown() ?? '';
}

interface ToolbarButtonProps {
  label: string;
  onClick: () => void;
  active?: boolean;
  disabled?: boolean;
  children: React.ReactNode;
}

function ToolbarButton({ label, onClick, active, disabled, children }: ToolbarButtonProps) {
  return (
    <Tooltip title={label}>
      <span>
        <IconButton
          aria-label={label}
          aria-pressed={active ?? undefined}
          size="small"
          onClick={onClick}
          disabled={disabled}
          color={active ? 'primary' : 'default'}
        >
          {children}
        </IconButton>
      </span>
    </Tooltip>
  );
}

function MarkdownPanelEditor({ value, onChange }: MarkdownPanelEditorProps) {
  const [mode, setMode] = useState<Mode>('wysiwyg');
  const [linkDialogOpen, setLinkDialogOpen] = useState(false);
  const [linkUrl, setLinkUrl] = useState('');
  const tableButtonRef = useRef<HTMLButtonElement | null>(null);
  const [tableMenuOpen, setTableMenuOpen] = useState(false);
  const [, setTick] = useState(0);

  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        link: { openOnClick: false, autolink: true }
      }),
      Table.configure({ resizable: true }),
      TableRow,
      TableHeader,
      TableCell,
      Markdown.configure({
        html: false,
        tightLists: true,
        breaks: false
      })
    ],
    content: value ?? '',
    onUpdate: ({ editor: e }) => {
      const md = getMarkdown(e);
      onChange(md.trim() ? md : undefined);
    }
  });

  useEffect(() => {
    if (!editor) return undefined;
    const bump = () => setTick((n) => n + 1);
    editor.on('transaction', bump);
    editor.on('selectionUpdate', bump);
    return () => {
      editor.off('transaction', bump);
      editor.off('selectionUpdate', bump);
    };
  }, [editor]);

  useEffect(() => {
    if (!editor || mode !== 'wysiwyg') return;
    const current = getMarkdown(editor);
    if ((value ?? '') !== current) {
      editor.commands.setContent(value ?? '', { emitUpdate: false });
    }
    // We only want to resync when switching back to WYSIWYG; intentionally omit `value`.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, editor]);

  function openLinkDialog() {
    if (!editor) return;
    const previous = (editor.getAttributes('link').href as string | undefined) ?? '';
    setLinkUrl(previous);
    setLinkDialogOpen(true);
  }

  function applyLink() {
    if (!editor) return;
    const url = linkUrl.trim();
    if (url) {
      editor.chain().focus().extendMarkRange('link').setLink({ href: url }).run();
    } else {
      editor.chain().focus().extendMarkRange('link').unsetLink().run();
    }
    setLinkDialogOpen(false);
  }

  function removeLink() {
    if (!editor) return;
    editor.chain().focus().extendMarkRange('link').unsetLink().run();
  }

  const inTable = editor?.isActive('table') ?? false;

  function runTableCommand(cmd: (chain: ReturnType<Editor['chain']>) => ReturnType<Editor['chain']>) {
    if (!editor) return;
    cmd(editor.chain().focus()).run();
    setTableMenuOpen(false);
  }

  return (
    <Box>
      <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1 }}>
        <ToggleButtonGroup
          size="small"
          exclusive
          value={mode}
          onChange={(_, val: Mode | null) => {
            if (val) setMode(val);
          }}
          aria-label="Editor mode"
        >
          <ToggleButton value="wysiwyg" aria-label="WYSIWYG editor">
            WYSIWYG
          </ToggleButton>
          <ToggleButton value="source" aria-label="Markdown source">
            Markdown
          </ToggleButton>
        </ToggleButtonGroup>
      </Stack>

      {mode === 'wysiwyg' ? (
        <Box>
          <Box
            sx={{
              display: 'flex',
              flexWrap: 'wrap',
              alignItems: 'center',
              gap: 0.25,
              mb: 1,
              p: 0.5,
              border: '1px solid',
              borderColor: 'divider',
              borderRadius: 1
            }}
          >
            <ToolbarButton
              label="Bold"
              active={editor?.isActive('bold') ?? false}
              onClick={() => editor?.chain().focus().toggleBold().run()}
              disabled={!editor}
            >
              <FormatBoldIcon fontSize="small" />
            </ToolbarButton>
            <ToolbarButton
              label="Italic"
              active={editor?.isActive('italic') ?? false}
              onClick={() => editor?.chain().focus().toggleItalic().run()}
              disabled={!editor}
            >
              <FormatItalicIcon fontSize="small" />
            </ToolbarButton>
            <Divider orientation="vertical" flexItem sx={{ mx: 0.5 }} />
            <ToolbarButton
              label="Heading 2"
              active={editor?.isActive('heading', { level: 2 }) ?? false}
              onClick={() => editor?.chain().focus().toggleHeading({ level: 2 }).run()}
              disabled={!editor}
            >
              <Box component="span" sx={{ fontWeight: 700, fontSize: '0.8rem' }}>
                H2
              </Box>
            </ToolbarButton>
            <ToolbarButton
              label="Heading 3"
              active={editor?.isActive('heading', { level: 3 }) ?? false}
              onClick={() => editor?.chain().focus().toggleHeading({ level: 3 }).run()}
              disabled={!editor}
            >
              <Box component="span" sx={{ fontWeight: 700, fontSize: '0.8rem' }}>
                H3
              </Box>
            </ToolbarButton>
            <Divider orientation="vertical" flexItem sx={{ mx: 0.5 }} />
            <ToolbarButton
              label="Bullet list"
              active={editor?.isActive('bulletList') ?? false}
              onClick={() => editor?.chain().focus().toggleBulletList().run()}
              disabled={!editor}
            >
              <FormatListBulletedIcon fontSize="small" />
            </ToolbarButton>
            <ToolbarButton
              label="Ordered list"
              active={editor?.isActive('orderedList') ?? false}
              onClick={() => editor?.chain().focus().toggleOrderedList().run()}
              disabled={!editor}
            >
              <FormatListNumberedIcon fontSize="small" />
            </ToolbarButton>
            <ToolbarButton
              label="Blockquote"
              active={editor?.isActive('blockquote') ?? false}
              onClick={() => editor?.chain().focus().toggleBlockquote().run()}
              disabled={!editor}
            >
              <FormatQuoteIcon fontSize="small" />
            </ToolbarButton>
            <Divider orientation="vertical" flexItem sx={{ mx: 0.5 }} />
            <ToolbarButton
              label="Inline code"
              active={editor?.isActive('code') ?? false}
              onClick={() => editor?.chain().focus().toggleCode().run()}
              disabled={!editor}
            >
              <CodeIcon fontSize="small" />
            </ToolbarButton>
            <ToolbarButton
              label="Code block"
              active={editor?.isActive('codeBlock') ?? false}
              onClick={() => editor?.chain().focus().toggleCodeBlock().run()}
              disabled={!editor}
            >
              <DataObjectIcon fontSize="small" />
            </ToolbarButton>
            <Divider orientation="vertical" flexItem sx={{ mx: 0.5 }} />
            <ToolbarButton
              label="Link"
              active={editor?.isActive('link') ?? false}
              onClick={openLinkDialog}
              disabled={!editor}
            >
              <LinkIcon fontSize="small" />
            </ToolbarButton>
            <ToolbarButton
              label="Remove link"
              onClick={removeLink}
              disabled={!editor || !editor.isActive('link')}
            >
              <LinkOffIcon fontSize="small" />
            </ToolbarButton>
            <Divider orientation="vertical" flexItem sx={{ mx: 0.5 }} />
            <Tooltip title="Table">
              <span>
                <IconButton
                  ref={tableButtonRef}
                  aria-label="Table"
                  aria-haspopup="menu"
                  aria-expanded={tableMenuOpen || undefined}
                  size="small"
                  color={inTable ? 'primary' : 'default'}
                  onClick={() => setTableMenuOpen(true)}
                  disabled={!editor}
                >
                  <TableChartIcon fontSize="small" />
                </IconButton>
              </span>
            </Tooltip>
            <Menu
              anchorEl={tableButtonRef.current}
              open={tableMenuOpen}
              onClose={() => setTableMenuOpen(false)}
              slotProps={{ paper: { sx: { minWidth: 200 } } }}
            >
              <MenuItem
                onClick={() =>
                  runTableCommand((c) =>
                    c.insertTable({ rows: 3, cols: 3, withHeaderRow: true })
                  )
                }
              >
                Insert table
              </MenuItem>
              <Divider />
              <MenuItem
                disabled={!inTable}
                onClick={() => runTableCommand((c) => c.addRowAfter())}
              >
                Add row below
              </MenuItem>
              <MenuItem
                disabled={!inTable}
                onClick={() => runTableCommand((c) => c.addRowBefore())}
              >
                Add row above
              </MenuItem>
              <MenuItem
                disabled={!inTable}
                onClick={() => runTableCommand((c) => c.deleteRow())}
              >
                Delete row
              </MenuItem>
              <Divider />
              <MenuItem
                disabled={!inTable}
                onClick={() => runTableCommand((c) => c.addColumnAfter())}
              >
                Add column after
              </MenuItem>
              <MenuItem
                disabled={!inTable}
                onClick={() => runTableCommand((c) => c.addColumnBefore())}
              >
                Add column before
              </MenuItem>
              <MenuItem
                disabled={!inTable}
                onClick={() => runTableCommand((c) => c.deleteColumn())}
              >
                Delete column
              </MenuItem>
              <Divider />
              <MenuItem
                disabled={!inTable}
                onClick={() => runTableCommand((c) => c.toggleHeaderRow())}
              >
                Toggle header row
              </MenuItem>
              <MenuItem
                disabled={!inTable}
                onClick={() => runTableCommand((c) => c.deleteTable())}
                sx={{ color: 'error.main' }}
              >
                Delete table
              </MenuItem>
            </Menu>
            <Divider orientation="vertical" flexItem sx={{ mx: 0.5 }} />
            <ToolbarButton
              label="Undo"
              onClick={() => editor?.chain().focus().undo().run()}
              disabled={!editor?.can().undo()}
            >
              <UndoIcon fontSize="small" />
            </ToolbarButton>
            <ToolbarButton
              label="Redo"
              onClick={() => editor?.chain().focus().redo().run()}
              disabled={!editor?.can().redo()}
            >
              <RedoIcon fontSize="small" />
            </ToolbarButton>
          </Box>
          <Box
            sx={{
              border: '1px solid',
              borderColor: 'divider',
              borderRadius: 1,
              p: 1.5,
              minHeight: 200,
              '& .ProseMirror': {
                outline: 'none',
                minHeight: 180,
                '& > *:first-of-type': { mt: 0 },
                '& > *:last-child': { mb: 0 },
                '& p': { my: 1 },
                '& h1, & h2, & h3, & h4, & h5, & h6': { mt: 2, mb: 1 },
                '& ul, & ol': { pl: 3, my: 1 },
                '& blockquote': {
                  borderLeft: '4px solid',
                  borderColor: 'divider',
                  pl: 2,
                  my: 1,
                  color: 'text.secondary'
                },
                '& code': {
                  fontFamily: 'monospace',
                  bgcolor: 'action.hover',
                  px: 0.5,
                  py: 0.25,
                  borderRadius: 0.5
                },
                '& pre': {
                  fontFamily: 'monospace',
                  bgcolor: 'action.hover',
                  p: 1.5,
                  borderRadius: 1,
                  overflow: 'auto',
                  my: 1
                },
                '& pre code': { bgcolor: 'transparent', p: 0 },
                '& a': { color: 'primary.main', textDecoration: 'underline' },
                '& table': {
                  borderCollapse: 'collapse',
                  tableLayout: 'fixed',
                  width: '100%',
                  my: 1,
                  overflow: 'hidden'
                },
                '& table td, & table th': {
                  border: '1px solid',
                  borderColor: 'divider',
                  padding: '6px 10px',
                  minWidth: '80px',
                  verticalAlign: 'top',
                  position: 'relative'
                },
                '& table th': {
                  bgcolor: 'action.hover',
                  fontWeight: 700,
                  textAlign: 'left'
                },
                '& table .selectedCell': {
                  bgcolor: 'action.selected'
                },
                '& table .column-resize-handle': {
                  position: 'absolute',
                  right: '-2px',
                  top: 0,
                  bottom: '-2px',
                  width: '4px',
                  bgcolor: 'primary.main',
                  pointerEvents: 'none'
                },
                '&.resize-cursor': { cursor: 'col-resize' }
              }
            }}
          >
            <EditorContent editor={editor} />
          </Box>
        </Box>
      ) : (
        <TextField
          fullWidth
          size="small"
          label="Markdown content"
          multiline
          minRows={6}
          value={value ?? ''}
          onChange={(e) => onChange(e.target.value || undefined)}
        />
      )}

      <Dialog
        open={linkDialogOpen}
        onClose={() => setLinkDialogOpen(false)}
        maxWidth="xs"
        fullWidth
      >
        <DialogTitle>Insert link</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            fullWidth
            size="small"
            label="URL"
            value={linkUrl}
            onChange={(e) => setLinkUrl(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault();
                applyLink();
              }
            }}
            sx={{ mt: 1 }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setLinkDialogOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={applyLink}>
            Apply
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}

export default MarkdownPanelEditor;
