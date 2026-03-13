import { useContext } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import {
  AppBar,
  AppBarProps,
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

import { ConfigContext, SeizuConfig, Neo4jSettings } from 'src/config.context';
import Logo from './Logo';
import Hidden from './Hidden';

interface DashboardNavbarProps extends Omit<AppBarProps, 'children'> {
  configUpdate?: SeizuConfig;
  setConfigUpdate: (config?: SeizuConfig) => void;
  setConfig: (config: SeizuConfig) => void;
  onMobileNavOpen: () => void;
  setAuth: (auth?: undefined) => void;
  setDriver: (driver?: undefined) => void;
  neo4jSettings?: Neo4jSettings;
}

function DashboardNavbar({
  configUpdate,
  setConfigUpdate,
  setConfig,
  onMobileNavOpen,
  setAuth,
  setDriver,
  neo4jSettings,
  ...rest
}: DashboardNavbarProps) {
  const { auth } = useContext(ConfigContext);
  const handleRefresh = () => {
    if (configUpdate) {
      setConfig(configUpdate);
    }
    setConfigUpdate(undefined);
  };

  const refresh = (
    <Button size="small" onClick={handleRefresh} endIcon={<Cached />}>
      Refresh
    </Button>
  );

  const logOut = () => {
    setAuth(undefined);
    setDriver(undefined);
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

export default DashboardNavbar;
