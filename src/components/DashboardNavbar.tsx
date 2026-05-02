import { useContext, useState } from 'react';
import {
  AppBar,
  AppBarProps,
  Box,
  IconButton,
  ListItemIcon,
  ListItemText,
  Menu,
  MenuItem,
  Toolbar,
  Tooltip,
  Typography
} from '@mui/material';
import LogoutIcon from '@mui/icons-material/Logout';
import MenuIcon from '@mui/icons-material/Menu';
import MenuOpenIcon from '@mui/icons-material/MenuOpen';

import { AuthConfigContext } from 'src/authConfig.context';
import { useCurrentUser } from 'src/hooks/useCurrentUser';
import { DASHBOARD_SIDEBAR_WIDTH_VAR } from 'src/components/dashboardLayoutConstants';
import Hidden from './Hidden';
import UserAvatar from './UserAvatar';

interface DashboardNavbarProps extends Omit<AppBarProps, 'children'> {
  onMobileNavOpen: () => void;
  onSidebarToggle?: () => void;
  sidebarCollapsed?: boolean;
}

function DashboardNavbar({
  onMobileNavOpen,
  onSidebarToggle,
  sidebarCollapsed = false,
  sx,
  ...rest
}: DashboardNavbarProps) {
  const currentUser = useCurrentUser();
  const { userManager } = useContext(AuthConfigContext);
  const [userMenuAnchor, setUserMenuAnchor] = useState<null | HTMLElement>(null);

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

  const userName = currentUser
    ? currentUser.email || currentUser.display_name || currentUser.user_id
    : '';

  const retVal = (
    <AppBar
      enableColorOnDark
      elevation={0}
      sx={[
        (theme) => ({
          transition: theme.transitions.create(['left', 'width'], {
            duration: theme.transitions.duration.shorter
          }),
          [theme.breakpoints.up('lg')]: {
            left: `var(${DASHBOARD_SIDEBAR_WIDTH_VAR})`,
            width: `calc(100% - var(${DASHBOARD_SIDEBAR_WIDTH_VAR}))`
          }
        }),
        ...(Array.isArray(sx) ? sx : [sx])
      ]}
      {...rest}
    >
      <Toolbar>
        {onSidebarToggle && (
          <Hidden>
            <Tooltip title={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}>
              <IconButton
                aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
                color="inherit"
                size="small"
                onClick={onSidebarToggle}
              >
                {sidebarCollapsed ? <MenuIcon /> : <MenuOpenIcon />}
              </IconButton>
            </Tooltip>
          </Hidden>
        )}
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
