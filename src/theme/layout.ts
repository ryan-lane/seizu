import type { Theme } from '@mui/material/styles';

export const CONTENT_CONTAINER_PADDING = {
  xs: 1.5,
  sm: 2
} as const;

export const contentContainerSx = {
  px: CONTENT_CONTAINER_PADDING
};

export const pageContentSx = {
  p: CONTENT_CONTAINER_PADDING
};

export function contentContainerRootStyles(theme: Theme) {
  return {
    paddingLeft: theme.spacing(CONTENT_CONTAINER_PADDING.xs),
    paddingRight: theme.spacing(CONTENT_CONTAINER_PADDING.xs),
    [theme.breakpoints.up('sm')]: {
      paddingLeft: theme.spacing(CONTENT_CONTAINER_PADDING.sm),
      paddingRight: theme.spacing(CONTENT_CONTAINER_PADDING.sm)
    }
  };
}
