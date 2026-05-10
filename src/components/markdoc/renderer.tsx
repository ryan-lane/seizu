// Security: keep Markdoc rendering safe by upholding these invariants:
//   1. Do not pass a `partials` config sourced from user input — `{% partial %}`
//      becomes a content-inclusion primitive otherwise.
//   2. Do not register custom tags that route variable values into `style`,
//      `dangerouslySetInnerHTML`, or URL props (`href`, `src`, `srcDoc`)
//      without validating the value. Variables flow in as React text by default,
//      which React escapes; attribute positions bypass that escaping. The link
//      and image node overrides below allow variable substitution into href/src
//      but apply an allowlist (see `safeSubstitutedUrl`) — keep the allowlist
//      tight and add new schemes only with explicit review.
//   3. The Markdoc tokenizer keeps markdown-it `html: false`, so raw HTML in
//      source content is rendered as escaped text, not executed. Don't enable
//      `html: true` on the renderer.
import * as React from 'react';
import Markdoc, { Tag, nodes } from '@markdoc/markdoc';
import {
  TableHead,
  TableBody,
  TableRow,
  TableCell,
  TableContainer,
  Table,
  Paper,
} from '@mui/material';

function MarkdocTable({ children }: { children?: React.ReactNode }) {
  return (
    <TableContainer component={Paper} variant="outlined" sx={{ my: 2 }}>
      <Table size="small" sx={{ borderCollapse: 'collapse' }}>
        {children}
      </Table>
    </TableContainer>
  );
}

function MarkdocHeadCell({ children }: { children?: React.ReactNode }) {
  return (
    <TableCell
      component="th"
      scope="col"
      sx={{
        whiteSpace: 'normal',
        border: '1px solid',
        borderColor: 'divider',
        fontWeight: 700,
        bgcolor: 'action.hover',
      }}
    >
      {children}
    </TableCell>
  );
}

function MarkdocCell({ children }: { children?: React.ReactNode }) {
  return (
    <TableCell sx={{ whiteSpace: 'normal', border: '1px solid', borderColor: 'divider' }}>
      {children}
    </TableCell>
  );
}

const markdocComponents = {
  MuiTable: MarkdocTable,
  MuiTableHead: TableHead,
  MuiTableBody: TableBody,
  MuiTableRow: TableRow,
  MuiTableHeadCell: MarkdocHeadCell,
  MuiTableCell: MarkdocCell,
};

const headingNode = {
  ...nodes.heading,
  transform(node: any, config: any) {
    const attributes = node.transformAttributes(config);
    const children = node.transformChildren(config);
    const level = Math.min((node.attributes.level ?? 1) + 1, 6);
    return new Tag(`h${level}`, attributes, children);
  },
};

const listNode = {
  ...nodes.list,
  transform(node: any, config: any) {
    const attributes = node.transformAttributes(config);
    const children = node.transformChildren(config);
    const ordered = node.attributes.ordered;
    const tag = ordered ? 'ol' : 'ul';
    const className = ordered ? 'mui-markdown-ol' : 'mui-markdown-ul';
    return new Tag(tag, { ...attributes, class: className }, children);
  },
};

// Substitute {%$name%} (or {% $name %}) inside markdown link/image URL
// strings. markdown-it tokenizes `[text](url)` into a literal href and does
// not re-scan the URL for Markdoc variables, so we do it here. The URL is
// URL-decoded first because markdown-it percent-encodes `{`, `%`, and spaces
// inside the href.
const URL_VAR_RE = /\{%\s*\$([a-z][a-z0-9_]*)\s*%\}/g;

// Allowlist of protocols permitted in URLs that were *modified* by variable
// substitution. Variable values come from end-user input (URL query string,
// autocomplete pick), so we apply a stricter check than markdown-it's
// blacklist: deny anything not explicitly permitted, including custom OS
// protocol handlers (slack://, vscode://, etc.) and any future scheme.
// Static editor-authored URLs are not re-validated here — they already passed
// markdown-it's validateLink at parse time.
const ALLOWED_SUBSTITUTED_PROTO_RE = /^(https?|mailto|tel):/i;
const SCHEME_RE = /^[a-z][a-z0-9+\-.]*:/i;
const SAFE_DATA_IMAGE_RE = /^data:image\/(gif|png|jpeg|webp);/i;

// Browsers (per the WHATWG URL spec) strip ASCII tab, LF, CR, and other C0
// control characters from `href` attributes at navigation time. Mirror that
// stripping before validation so a value like "java\tscript:alert(1)" cannot
// slip past the scheme check (the embedded tab makes SCHEME_RE fail to match,
// so it would otherwise be treated as a relative URL) and then resolve to
// `javascript:` in the browser after the tab is removed. We return the
// normalized form so the rendered href is also clean.
const URL_CONTROL_CHARS_RE = /[\u0000-\u001F\u007F]/g;

function safeSubstitutedUrl(url: string): string {
  const normalized = url.replace(URL_CONTROL_CHARS_RE, '').trim();
  if (!normalized) return '#';
  // Relative URLs (no scheme) are always safe — they resolve under the
  // current page's origin.
  if (!SCHEME_RE.test(normalized)) return normalized;
  if (ALLOWED_SUBSTITUTED_PROTO_RE.test(normalized)) return normalized;
  if (SAFE_DATA_IMAGE_RE.test(normalized)) return normalized;
  return '#';
}

function substituteUrlVars(
  url: string,
  variables: Record<string, unknown>,
): { value: string; changed: boolean } {
  let decoded: string;
  try {
    decoded = decodeURIComponent(url);
  } catch {
    decoded = url;
  }
  let changed = false;
  const value = decoded.replace(URL_VAR_RE, (_match, name) => {
    changed = true;
    const v = variables[name];
    return v != null ? String(v) : '';
  });
  return { value, changed };
}

const linkNode = {
  ...nodes.link,
  transform(node: any, config: any) {
    const attributes = node.transformAttributes(config);
    const children = node.transformChildren(config);
    if (typeof attributes.href === 'string') {
      const { value, changed } = substituteUrlVars(attributes.href, config.variables ?? {});
      if (changed) attributes.href = safeSubstitutedUrl(value);
    }
    return new Tag('a', attributes, children);
  },
};

const imageNode = {
  ...nodes.image,
  transform(node: any, config: any) {
    const attributes = node.transformAttributes(config);
    if (typeof attributes.src === 'string') {
      const { value, changed } = substituteUrlVars(attributes.src, config.variables ?? {});
      if (changed) attributes.src = safeSubstitutedUrl(value);
    }
    return new Tag('img', attributes);
  },
};

const markdocNodes = {
  heading: headingNode,
  list: listNode,
  link: linkNode,
  image: imageNode,
  table: { ...nodes.table, render: 'MuiTable' },
  thead: { ...nodes.thead, render: 'MuiTableHead' },
  tbody: { ...nodes.tbody, render: 'MuiTableBody' },
  tr: { ...nodes.tr, render: 'MuiTableRow' },
  th: { ...nodes.th, render: 'MuiTableHeadCell' },
  td: { ...nodes.td, render: 'MuiTableCell' },
};

export interface MarkdocRendererProps {
  source: string;
  variables?: Record<string, string>;
}

export function MarkdocRenderer({ source, variables }: MarkdocRendererProps) {
  const rendered = React.useMemo(() => {
    const ast = Markdoc.parse(source ?? '');
    const content = Markdoc.transform(ast, {
      variables: variables ?? {},
      nodes: markdocNodes,
    });
    return Markdoc.renderers.react(content, React, { components: markdocComponents });
  }, [source, variables]);

  return <>{rendered}</>;
}
