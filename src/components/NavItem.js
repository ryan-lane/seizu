import React from 'react';
import {
  NavLink as RouterLink,
  matchPath,
  useLocation
} from 'react-router-dom';
import ExpandLess from '@mui/icons-material/ExpandLess';
import ExpandMore from '@mui/icons-material/ExpandMore';
import { makeStyles } from '@mui/styles';
import PropTypes from 'prop-types';
import { Button, Collapse, List, ListItem } from '@mui/material';

const useStyles = makeStyles((theme) => ({
  nested: {
    paddingLeft: theme.spacing(2)
  }
}));

function NavItem({ href, icon: Icon, title, subItems, ...rest }) {
  const location = useLocation();

  const classes = useStyles();

  const [open, setOpen] = React.useState(true);

  if (subItems === undefined) {
    const active = href
      ? !!matchPath(
          {
            path: href,
            exact: true
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
            py: 0
          }}
          {...rest}
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
            startIcon={Icon && <Icon size="20" />}
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
        button
        onClick={handleClick}
        sx={{
          display: 'flex',
          py: 0
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
          startIcon={Icon && <Icon size="20" />}
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
              className={classes.nested}
            />
          ))}
        </List>
      </Collapse>
    </div>
  );
}

NavItem.propTypes = {
  href: PropTypes.string,
  icon: PropTypes.elementType,
  title: PropTypes.string,
  subItems: PropTypes.array
};

export default NavItem;
