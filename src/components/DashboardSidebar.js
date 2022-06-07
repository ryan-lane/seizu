import { useContext } from 'react';
import PropTypes from 'prop-types';
import { Box, Divider, Drawer, List } from '@mui/material';
import Dashboard from '@mui/icons-material/Dashboard';
import Insights from '@mui/icons-material/Insights';
import Article from '@mui/icons-material/Article';
import Storage from '@mui/icons-material/Storage';
import MenuBook from '@mui/icons-material/MenuBook';
import NavItem from 'src/components/NavItem';
import Hidden from 'src/components/Hidden';
import { ConfigContext } from 'src/config.context';

function DashboardSidebar({ onMobileClose, openMobile }) {
  const { config } = useContext(ConfigContext);
  const { reports } = config.config;
  const reportSubitems = [];

  Object.keys(reports).forEach((key) => {
    const report = reports[key];
    reportSubitems.push({
      href: `/app/reports/${key}`,
      title: report.name,
      icon: Article
    });
  });

  const items = [
    {
      href: '/app/dashboard',
      icon: Dashboard,
      title: 'Dashboard'
    },
    {
      href: '/app/reports',
      icon: Insights,
      title: 'Reports',
      subItems: reportSubitems
    }
  ];

  const adminItems = [
    {
      href: '/app/neo4j',
      icon: Storage,
      title: 'Neo4J Console'
    },
    {
      href: '/app/documentation',
      icon: MenuBook,
      title: 'Documentation'
    }
  ];

  const content = (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%'
      }}
    >
      <Box sx={{ p: 2 }}>
        <List>
          {items.map((item) => (
            <NavItem
              href={item.href}
              key={item.title}
              title={item.title}
              icon={item.icon}
              subItems={item.subItems}
            />
          ))}
        </List>
        <Divider />
        <List>
          {adminItems.map((item) => (
            <NavItem
              href={item.href}
              key={item.title}
              title={item.title}
              icon={item.icon}
              subItems={item.subItems}
            />
          ))}
        </List>
      </Box>
    </Box>
  );

  return (
    <>
      <Hidden lgUp>
        <Drawer
          anchor="left"
          onClose={onMobileClose}
          open={openMobile}
          variant="temporary"
          PaperProps={{
            sx: {
              width: 256
            }
          }}
        >
          {content}
        </Drawer>
      </Hidden>
      <Hidden>
        <Drawer
          anchor="left"
          open
          variant="persistent"
          PaperProps={{
            sx: {
              width: 256,
              top: 64,
              height: 'calc(100% - 64px)'
            }
          }}
        >
          {content}
        </Drawer>
      </Hidden>
    </>
  );
}

DashboardSidebar.propTypes = {
  onMobileClose: PropTypes.func,
  openMobile: PropTypes.bool
};

DashboardSidebar.defaultProps = {
  onMobileClose: () => {},
  openMobile: false
};

export default DashboardSidebar;
