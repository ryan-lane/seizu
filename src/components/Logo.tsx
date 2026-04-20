import React from 'react';
import { useTheme } from '@mui/material/styles';

function Logo(props: React.ImgHTMLAttributes<HTMLImageElement>) {
  const theme = useTheme();
  // Logo sits on an AppBar using palette.primary. Pick the lockup whose
  // wordmark color matches primary.contrastText so it reads correctly:
  // dark mode → Starlight primary (light) → black wordmark;
  // light mode → Starlight-shifted primary (dark) → white wordmark.
  const src =
    theme.palette.mode === 'dark'
      ? '/static/images/logo-horizontal-black.svg'
      : '/static/images/logo-horizontal-white.svg';
  return <img alt="Seizu" src={src} height="50" {...props} />;
}

export default Logo;
