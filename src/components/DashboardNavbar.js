import { useContext } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import PropTypes from 'prop-types';
import {
  AppBar,
  Box,
  Button,
  IconButton,
  Link,
  Snackbar,
  Toolbar,
  Typography
} from '@mui/material';
import Cached from '@mui/icons-material/Cached';
import MenuIcon from '@mui/icons-material/Menu';

import { ConfigContext } from 'src/config.context';
import Logo from './Logo';
import Hidden from './Hidden';

function DashboardNavbar({
  configUpdate,
  setConfigUpdate,
  setConfig,
  onMobileNavOpen,
  setAuth,
  setDriver,
  neo4jSettings,
  ...rest
}) {
  const { auth } = useContext(ConfigContext);
  const handleRefresh = () => {
    setConfig(configUpdate);
    setConfigUpdate();
  };

  const refresh = (
    <Button size="small" onClick={handleRefresh} endIcon={<Cached />}>
      Refresh
    </Button>
  );

  const logOut = () => {
    setAuth();
    setDriver();
  };

  const logOutLink = (
    <>
      (
      <Link
        onClick={logOut}
        color="inherit"
        variant="subtitle2"
        underline="always"
        href="#"
      >
        Log Out
      </Link>
      )
    </>
  );

  const retVal = (
    <AppBar enableColorOnDark elevation={0} {...rest}>
      <Toolbar>
        <RouterLink to="/">
          <Logo />
        </RouterLink>
        <Snackbar
          open={configUpdate !== undefined}
          anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
          message="Settings have changed."
          action={refresh}
        />
        <Box sx={{ flexGrow: 1 }} />
        <Typography variant="subtitle2">
          Logged in as {auth?.username}{' '}
          {neo4jSettings?.authMode !== 'auto' && logOutLink}
        </Typography>
        <Hidden lgUp>
          <IconButton color="inherit" onClick={onMobileNavOpen}>
            <MenuIcon />
          </IconButton>
        </Hidden>
      </Toolbar>
    </AppBar>
  );
  return retVal;
}

DashboardNavbar.propTypes = {
  configUpdate: PropTypes.object,
  setConfigUpdate: PropTypes.func,
  setConfig: PropTypes.func,
  onMobileNavOpen: PropTypes.func,
  setAuth: PropTypes.func,
  setDriver: PropTypes.func,
  neo4jSettings: PropTypes.object
};

export default DashboardNavbar;
