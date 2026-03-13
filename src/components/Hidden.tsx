import { ReactNode } from 'react';
import useMediaQuery from '@mui/material/useMediaQuery';
import { Theme } from '@mui/material/styles';

interface HiddenProps {
  lgUp?: boolean;
  children?: ReactNode;
}

function Hidden(props: HiddenProps) {
  const { lgUp, children } = props;
  const hidden = useMediaQuery((theme: Theme) => {
    if (lgUp) {
      return theme.breakpoints.up('lg');
    }
    return theme.breakpoints.down('lg');
  });
  return hidden ? null : children;
}

export default Hidden;
