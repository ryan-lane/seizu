import { Helmet } from 'react-helmet';
import {
  Box,
  Container,
  Divider,
  Grid,
  List,
  ListItem,
  Paper,
  Typography,
  Table,
  TableHead,
  TableBody,
  TableCell,
  TableContainer,
  TableRow
} from '@mui/material';
import { ThreeDots } from 'react-loader-spinner';

import { useAllReports } from 'src/hooks/useReportsApi';

function Documentation() {
  const { reports, loading } = useAllReports();

  if (loading) {
    return <ThreeDots color="#2BAD60" height="100" width="100" />;
  }

  const metricRows = [];
  const metrics = {};

  reports.forEach((report) => {
    report.rows.forEach((row) => {
      row.panels.forEach((panel) => {
        if (panel.metric === undefined || metrics[panel.metric] !== undefined) {
          return;
        }
        const params = [];
        if (panel.params !== undefined) {
          panel.params.forEach((input) => {
            params.push(input.name);
          });
        }
        metrics[panel.metric] = {
          params,
          type: panel.type
        };
      });
    });
  });

  Object.keys(metrics).forEach((metricName) => {
    const panel = metrics[metricName];
    const params = [];
    const fullMetrics = [];
    panel.params.forEach((paramName) => {
      params.push(
        <ListItem>
          <Typography variant="body1">{paramName}</Typography>
        </ListItem>
      );
    });
    if (panel.type === 'progress') {
      fullMetrics.push(
        <ListItem>
          <Typography variant="body1">{metricName}.numerator</Typography>
        </ListItem>
      );
      fullMetrics.push(
        <ListItem>
          <Typography variant="body1">{metricName}.denominator</Typography>
        </ListItem>
      );
    } else if (panel.type === 'count') {
      fullMetrics.push(
        <ListItem>
          <Typography variant="body1">{metricName}.total</Typography>
        </ListItem>
      );
    }
    metricRows.push(
      <TableRow key={panel.metric}>
        <TableCell style={{ verticalAlign: 'top' }}>
          <List disablePadding dense>
            {fullMetrics}
          </List>
        </TableCell>
        <TableCell style={{ verticalAlign: 'top' }}>
          <List disablePadding dense>
            {params}
          </List>
        </TableCell>
      </TableRow>
    );
  });

  return (
    <>
      <Helmet>
        <title>Dashboard Configuration Documentation | Seizu</title>
      </Helmet>
      <Box
        sx={{
          backgroundColor: 'background.default',
          minHeight: '100%',
          py: 3
        }}
      >
        <Grid container>
          <Container maxWidth={false} sx={{ pb: 2 }}>
            <Paper elevation={1} sx={{ p: 2 }}>
              <Typography gutterBottom variant="h2">
                Configured metrics
              </Typography>
              <Divider />
              <TableContainer sx={{ pl: 2, pt: 2 }}>
                <Table
                  size="small"
                  sx={{ maxWidth: '50%' }}
                  aria-label="configured-metrics"
                >
                  <TableHead>
                    <TableRow>
                      <TableCell padding="none">
                        <Typography variant="h4">Metric</Typography>
                      </TableCell>
                      <TableCell padding="none">
                        <Typography variant="h4">Metric Tags</Typography>
                      </TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>{metricRows}</TableBody>
                </Table>
              </TableContainer>
            </Paper>
          </Container>
        </Grid>
      </Box>
    </>
  );
}

export default Documentation;
