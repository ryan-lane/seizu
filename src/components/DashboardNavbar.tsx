import { Link as RouterLink } from 'react-router-dom';
import {
  AppBar,
  AppBarProps,
  Box,
  Button,
  IconButton,
  Snackbar,
  Toolbar
} from '@mui/material';
import Cached from '@mui/icons-material/Cached';
import MenuIcon from '@mui/icons-material/Menu';

import { SeizuConfig } from 'src/config.context';
import Logo from './Logo';
import Hidden from './Hidden';

interface DashboardNavbarProps extends Omit<AppBarProps, 'children'> {
  configUpdate?: SeizuConfig;
  setConfigUpdate: (config?: SeizuConfig) => void;
  setConfig: (config: SeizuConfig) => void;
  onMobileNavOpen: () => void;
}

function DashboardNavbar({
  configUpdate,
  setConfigUpdate,
  setConfig,
  onMobileNavOpen,
  ...rest
}: DashboardNavbarProps) {
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
