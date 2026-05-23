import type { ReactNode } from 'react';
import { Box, Typography } from '@mui/material';

// Standard list-view top bar: an h1 title on the left and an optional action
// (typically a `<Button variant="contained">`) on the right.

interface ListPageHeaderProps {
  /** A string is wrapped in `<Typography variant="h1">`; a node is rendered as-is. */
  title: ReactNode;
  /** Right-aligned action(s), e.g. a "New …" button. */
  action?: ReactNode;
}

export default function ListPageHeader({ title, action }: ListPageHeaderProps) {
  return (
    <Box
      sx={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        mb: 3,
      }}
    >
      {typeof title === 'string' ? (
        <Typography variant="h1">{title}</Typography>
      ) : (
        title
      )}
      {action}
    </Box>
  );
}
