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

  const handleClick = () => {
    setOpen(!open);
  };

  return (
    <div>
      <ListItem
        disableGutters
        onClick={handleClick}
        sx={{
          display: 'flex',
          py: 0,
          cursor: 'pointer'
        }}
      >
        <Button
          sx={{
            color: 'text.secondary',
            fontWeight: 'medium',
            justifyContent: 'flex-start',
            letterSpacing: 0,
            textTransform: 'none',
            width: '100%',
            '& svg': {
              mr: 1
            }
          }}
          startIcon={Icon && <Icon fontSize="small" />}
        >
          <span>{title}</span>
        </Button>
        {open ? <ExpandMore /> : <ExpandLess />}
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
