import { Box, Divider, Drawer, List } from '@mui/material';
import Dashboard from '@mui/icons-material/Dashboard';
import Insights from '@mui/icons-material/Insights';
import Article from '@mui/icons-material/Article';
import MenuBook from '@mui/icons-material/MenuBook';
import Terminal from '@mui/icons-material/Terminal';
import Schedule from '@mui/icons-material/Schedule';
import Extension from '@mui/icons-material/Extension';
import NavItem from 'src/components/NavItem';
import Hidden from 'src/components/Hidden';
import { NavItemData } from 'src/components/NavItem';
import { useReportsList } from 'src/hooks/useReportsApi';

interface DashboardSidebarProps {
  onMobileClose?: () => void;
  openMobile?: boolean;
}

function DashboardSidebar({ onMobileClose = () => {}, openMobile = false }: DashboardSidebarProps) {
  const { reports } = useReportsList();
  const reportSubitems: NavItemData[] = reports
    .filter((report) => report.pinned)
    .map((report) => ({
      href: `/app/reports/${report.report_id}`,
      title: report.name,
      icon: Article
    }));

  const items: NavItemData[] = [
    {
      href: '/app/dashboard',
      icon: Dashboard,
      title: 'Dashboard'
    },
    {
      href: '/app/reports',
      icon: Insights,
      title: 'Reports',
      subItems: reportSubitems.length > 0 ? reportSubitems : undefined
    },
    {
      href: '/app/query-console',
      icon: Terminal,
      title: 'Query Console'
    },
    {
      href: '/app/scheduled-queries',
      icon: Schedule,
      title: 'Scheduled Queries'
    },
    {
      href: '/app/toolsets',
      icon: Extension,
      title: 'MCP Toolsets'
    }
  ];

  const adminItems: NavItemData[] = [
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

export default DashboardSidebar;
