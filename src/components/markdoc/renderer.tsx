// Security: keep Markdoc rendering safe by upholding these invariants:
//   1. Do not pass a `partials` config sourced from user input — `{% partial %}`
//      becomes a content-inclusion primitive otherwise.
//   2. Do not register custom tags that route variable values into `style`,
//      `dangerouslySetInnerHTML`, or URL props (`href`, `src`, `srcDoc`)
//      without validating the value. Variables flow in as React text by default,
//      which React escapes; attribute positions bypass that escaping.
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

const markdocNodes = {
  heading: headingNode,
  list: listNode,
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
