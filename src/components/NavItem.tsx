import React from 'react';
import {
  NavLink as RouterLink,
  matchPath,
  useLocation
} from 'react-router-dom';
import ExpandLess from '@mui/icons-material/ExpandLess';
import ExpandMore from '@mui/icons-material/ExpandMore';
import { Button, Collapse, List, ListItem, SxProps, Theme } from '@mui/material';
import { SvgIconComponent } from '@mui/icons-material';

export interface NavItemData {
  href?: string;
  icon?: SvgIconComponent;
  title: string;
  subItems?: NavItemData[];
}

interface NavItemProps extends NavItemData {
  sx?: SxProps<Theme>;
}

function NavItem({ href, icon: Icon, title, subItems, ...rest }: NavItemProps) {
  const location = useLocation();

  const [open, setOpen] = React.useState(true);

  if (subItems === undefined) {
    const active = href
      ? !!matchPath(
          {
            path: href,
            end: true
          },
          location.pathname
        )
      : false;

    return (
      <div>
        <ListItem
          disableGutters
          sx={{
            display: 'flex',
            py: 0,
            ...(rest.sx as object)
          }}
        >
          <Button
            component={RouterLink}
            sx={{
              color: 'text.secondary',
              fontWeight: 'medium',
              justifyContent: 'flex-start',
              letterSpacing: 0,
              textTransform: 'none',
              width: '100%',
              ...(active && {
                color: 'primary.main'
              }),
              '& svg': {
                mr: 1
              }
            }}
            to={href}
            startIcon={Icon && <Icon fontSize="small" />}
          >
            <span>{title}</span>
          </Button>
        </ListItem>
      </div>
    );
  }

  return (
    <div>
      <ListItem
        disableGutters
        sx={{
          display: 'flex',
          py: 0
        }}
      >
        <Button
          component={href ? RouterLink : 'button'}
          to={href}
          sx={{
            color: 'text.secondary',
            fontWeight: 'medium',
            justifyContent: 'flex-start',
            letterSpacing: 0,
            textTransform: 'none',
            flex: 1,
            '& svg': {
              mr: 1
            }
          }}
          startIcon={Icon && <Icon fontSize="small" />}
        >
          <span>{title}</span>
        </Button>
        <Button
          onClick={() => setOpen(!open)}
          sx={{ minWidth: 0, px: 0.5, color: 'text.secondary' }}
        >
          {open ? <ExpandMore /> : <ExpandLess />}
        </Button>
      </ListItem>
      <Collapse in={open} timeout="auto" unmountOnExit>
        <List disablePadding>
          {subItems.map((item) => (
            <NavItem
              href={item.href}
              key={item.title}
              title={item.title}
              icon={item.icon}
              sx={{ pl: 2 }}
            />
          ))}
        </List>
      </Collapse>
    </div>
  );
}

export default NavItem;
