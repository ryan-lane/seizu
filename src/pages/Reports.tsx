import { useContext } from 'react';
import { useParams } from 'react-router-dom';
import { Box, Typography } from '@mui/material';
import { ThreeDots } from 'react-loader-spinner';
import Error from '@mui/icons-material/Error';

import { ConfigContext } from 'src/config.context';
import ReportView from 'src/components/ReportView';
import { useReport } from 'src/hooks/useReportsApi';

function Reports() {
  const { id } = useParams();
  const { config } = useContext(ConfigContext);
  const { report, loading, error } = useReport(id);

  if (loading) {
    return <ThreeDots color="#2BAD60" height="100" width="100" />;
  }

  if (error || !report) {
    return (
      <Box sx={{ p: 3, display: 'flex', alignItems: 'center', gap: 1 }}>
        <Error />
        <Typography>Failed to load report</Typography>
      </Box>
    );
  }

  return (
    <ReportView
      report={report}
      queries={config.config.queries}
      title={report.name}
    />
  );
}

export default Reports;
