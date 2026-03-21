import { Navigate } from 'react-router-dom';
import DashboardLayout from 'src/components/DashboardLayout';
import MainLayout from 'src/components/MainLayout';
import OidcCallback from 'src/components/OidcCallback';
import Dashboard from 'src/pages/Dashboard';
import Reports from 'src/pages/Reports';
import ReportHistory from 'src/pages/ReportHistory';
import ReportVersionView from 'src/pages/ReportVersionView';
import ReportsList from 'src/pages/ReportsList';
import Documentation from 'src/pages/Documentation';
import NotFound from 'src/pages/NotFound';
import QueryConsole from 'src/pages/QueryConsole';

const routes = [
  {
    path: '/auth/callback',
    element: <OidcCallback />
  },
  {
    path: 'app',
    element: <DashboardLayout />,
    children: [
      { path: 'dashboard', element: <Dashboard /> },
      { path: 'reports', element: <ReportsList /> },
      { path: 'reports/:id', element: <Reports /> },
      { path: 'reports/:id/history', element: <ReportHistory /> },
      { path: 'reports/:id/versions/:version', element: <ReportVersionView /> },
      { path: 'query-console', element: <QueryConsole /> },
      { path: 'documentation', element: <Documentation /> },
      { path: '*', element: <Navigate to="/404" /> }
    ]
  },
  {
    path: '/',
    element: <MainLayout />,
    children: [
      { path: '404', element: <NotFound /> },
      { path: '/', element: <Navigate to="/app/dashboard" /> },
      { path: '*', element: <Navigate to="/404" /> }
    ]
  }
];

export default routes;
