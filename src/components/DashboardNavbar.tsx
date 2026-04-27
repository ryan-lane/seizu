import { useContext, useState } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import {
  AppBar,
  AppBarProps,
  Box,
  Button,
  IconButton,
  ListItemIcon,
  ListItemText,
  Menu,
  MenuItem,
  Snackbar,
  Toolbar,
  Tooltip,
  Typography
} from '@mui/material';
import Cached from '@mui/icons-material/Cached';
import LogoutIcon from '@mui/icons-material/Logout';
import MenuIcon from '@mui/icons-material/Menu';

import { SeizuConfig } from 'src/config.context';
import { AuthConfigContext } from 'src/authConfig.context';
import { useCurrentUser } from 'src/hooks/useCurrentUser';
import Logo from './Logo';
import Hidden from './Hidden';
import UserAvatar from './UserAvatar';

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
  const currentUser = useCurrentUser();
  const { userManager } = useContext(AuthConfigContext);
  const [userMenuAnchor, setUserMenuAnchor] = useState<null | HTMLElement>(null);

  const handleRefresh = () => {
    if (configUpdate) {
      setConfig(configUpdate);
    }
    setConfigUpdate(undefined);
  };

  const handleLogout = async () => {
    setUserMenuAnchor(null);
    if (!userManager) return;

    try {
      await userManager.signoutRedirect({
        post_logout_redirect_uri: window.location.origin
      });
    } catch {
      await userManager.removeUser();
      window.location.assign('/');
    }
  };

  const refresh = (
    <Button size="small" onClick={handleRefresh} endIcon={<Cached />}>
      Refresh
    </Button>
  );

  const userName = currentUser
    ? currentUser.email || currentUser.display_name || currentUser.user_id
    : '';

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
        {currentUser && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, ml: 1 }}>
            <Typography variant="body2" color="inherit">
              {userName}
            </Typography>
            <Tooltip title="User menu">
              <IconButton
                aria-label="User menu"
                color="inherit"
                size="small"
                onClick={(event) => setUserMenuAnchor(event.currentTarget)}
              >
                <UserAvatar name={userName} />
              </IconButton>
            </Tooltip>
            <Menu
              anchorEl={userMenuAnchor}
              open={!!userMenuAnchor}
              onClose={() => setUserMenuAnchor(null)}
              anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
              transformOrigin={{ vertical: 'top', horizontal: 'right' }}
              slotProps={{ paper: { sx: { minWidth: 220 } } }}
            >
              <Box sx={{ px: 2, py: 1 }}>
                <Typography variant="body2" fontWeight={600}>
                  {userName}
                </Typography>
              </Box>
              {userManager && (
                <MenuItem onClick={handleLogout}>
                  <ListItemIcon>
                    <LogoutIcon fontSize="small" />
                  </ListItemIcon>
                  <ListItemText>Log out</ListItemText>
                </MenuItem>
              )}
            </Menu>
          </Box>
        )}
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
