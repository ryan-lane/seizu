import type { ReactNode } from 'react';
import { Box, CircularProgress, Typography } from '@mui/material';
import ErrorIcon from '@mui/icons-material/Error';

// Standard loading/error gate for list views: a centered spinner while
// loading, an error icon + message on failure, otherwise the content.

interface ListViewStateProps {
  loading: boolean;
  error?: unknown;
  errorMessage?: string;
  children: ReactNode;
}

export default function ListViewState({
  loading,
  error,
  errorMessage = 'Failed to load',
  children,
}: ListViewStateProps) {
  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <ErrorIcon />
        <Typography>{errorMessage}</Typography>
      </Box>
    );
  }

  return <>{children}</>;
}
