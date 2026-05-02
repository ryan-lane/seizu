import { Box, CircularProgress, Typography } from '@mui/material';

import ReportView from 'src/components/ReportView';
import { useDashboardReport } from 'src/hooks/useReportsApi';
import { pageContentSx } from 'src/theme/layout';

function Dashboard() {
  const { report, queryCapabilities, loading } = useDashboardReport();

  if (loading || (report && queryCapabilities === undefined)) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (!report) {
    return (
      <Box sx={pageContentSx}>
        <Typography>No dashboard configured.</Typography>
      </Box>
    );
  }

  return (
    <ReportView
      report={report}
      title="Dashboard"
      queryCapabilities={queryCapabilities}
      boxSx={{ backgroundColor: 'background.default', minHeight: '100%', py: 3 }}
    />
  );
}

export default Dashboard;
