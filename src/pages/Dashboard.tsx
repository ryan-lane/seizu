import { Box, Typography } from '@mui/material';
import { ThreeDots } from 'react-loader-spinner';

import ReportView from 'src/components/ReportView';
import { useDashboardReport } from 'src/hooks/useReportsApi';

function Dashboard() {
  const { report, loading } = useDashboardReport();

  if (loading) {
    return <ThreeDots color="#2BAD60" height="100" width="100" />;
  }

  if (!report) {
    return (
      <Box sx={{ p: 3 }}>
        <Typography>No dashboard configured.</Typography>
      </Box>
    );
  }

  return (
    <ReportView
      report={report}
      title="Dashboard"
      boxSx={{ backgroundColor: 'background.default', minHeight: '100%', py: 3 }}
    />
  );
}

export default Dashboard;
