import PropTypes from 'prop-types';
import useMediaQuery from '@mui/material/useMediaQuery';

function Hidden(props) {
  const { lgUp, children } = props;
  const hidden = useMediaQuery((theme) => {
    if (lgUp) {
      return theme.breakpoints.up('lg');
    }
    return theme.breakpoints.down('lg');
  });
  return hidden ? null : children;
}

Hidden.propTypes = {
  lgUp: PropTypes.bool,
  children: PropTypes.node
};

export default Hidden;
