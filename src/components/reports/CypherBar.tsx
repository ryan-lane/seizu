import { useEffect, useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  CardHeader,
  CircularProgress,
  Divider,
  IconButton,
  Grid,
  Typography
} from '@mui/material';
import { useTheme } from '@mui/material/styles';
import Info from '@mui/icons-material/Info';
import Error from '@mui/icons-material/Error';
import { BarChart } from '@mui/x-charts/BarChart';
import { chartColorsFor } from 'src/theme/brand';
import { useLazyCypherQuery, QueryRecord } from 'src/hooks/useCypherQuery';
import CypherDetails from 'src/components/reports/CypherDetails';
import QueryValidationBadge from 'src/components/reports/QueryValidationBadge';

interface BarSettings {
  legend?: string;
}

interface CypherBarProps {
  cypher?: string;
  params?: Record<string, unknown>;
  caption?: string;
  barSettings?: BarSettings;
  details?: Record<string, unknown>;
  needInputs?: string[];
}

export default function CypherBar({
  cypher,
  params,
  caption,
  barSettings,
  details,
  needInputs
}: CypherBarProps) {
  const theme = useTheme();
  const [open, setOpen] = useState(false);

  const [runQuery, { loading, error, records, first, warnings, queryErrors }] =
    useLazyCypherQuery(cypher);

  useEffect(() => {
    if (needInputs === undefined || needInputs.length === 0) {
      runQuery(params);
    }
  }, [cypher, params, runQuery]);

  if (cypher === undefined) {
    return (
      <Card>
        <Grid container spacing={0} direction="column" alignItems="center">
          <CardHeader title={caption} />
        </Grid>
        <Divider />
        <Grid container spacing={0} direction="column" alignItems="center">
          <CardContent>
            <Error />
            <Typography variant="body2">Missing cypher query</Typography>
          </CardContent>
        </Grid>
      </Card>
    );
  }

  if (needInputs !== undefined && needInputs.length > 0) {
    return (
      <Card>
        <Grid container spacing={0} direction="column" alignItems="center">
          <CardHeader title={caption} />
        </Grid>
        <Divider />
        <Grid container spacing={0} direction="column" alignItems="center">
          <CardContent>
            <Typography variant="body2" align="center">
              (Set {needInputs.join(', ')})
            </Typography>
          </CardContent>
        </Grid>
      </Card>
    );
  }

  if (error) {
    return (
      <Typography variant="body2">
        Failed to load requested data, please reload.
      </Typography>
    );
  }

  if (queryErrors.length > 0) {
    return (
      <Card>
        <Grid container direction="column" alignItems="center">
          <CardHeader title={caption} />
        </Grid>
        <Divider />
        <QueryValidationBadge errors={queryErrors} warnings={warnings} />
        <Grid container spacing={0} direction="column" alignItems="center">
          <CardContent>
            <Typography variant="h4" align="center">N/A</Typography>
            <Typography variant="body2" align="center">Query validation failed</Typography>
          </CardContent>
        </Grid>
      </Card>
    );
  }

  if (loading || records === undefined) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', p: 4 }}>
        <CircularProgress size={40} />
      </Box>
    );
  }

  if (first === undefined) {
    return (
      <Card>
        <Grid container spacing={0} direction="column" alignItems="center">
          <CardHeader title={caption} />
        </Grid>
        <Divider />
        <Grid container spacing={0} direction="column" alignItems="center">
          <CardContent>
            <Typography variant="h4">N/A</Typography>
          </CardContent>
        </Grid>
      </Card>
    );
  }

  const mungedRecords: Record<string, string | number>[] = [];
  for (let i = 0; i < records.length; i++) {
    const data = records[i];
    let mungedData: Record<string, unknown>;
    const dataDetails = data['details'] as QueryRecord & { properties?: QueryRecord };
    if (dataDetails.properties === undefined) {
      mungedData = dataDetails;
    } else {
      mungedData = dataDetails.properties;
    }
    const flat: Record<string, string | number> = {};
    Object.keys(mungedData).forEach((key) => {
      const val = mungedData[key];
      if (Array.isArray(val)) {
        flat[key] = (val as unknown[]).join(', ');
      } else if (val === null || val === undefined) {
        flat[key] = 0;
      } else {
        flat[key] = val as string | number;
      }
    });
    mungedRecords.push(flat);
  }

  const hasLegend = !!barSettings?.legend;
  // Object literal without explicit React.CSSProperties type — ChartsTextStyle is stricter
  const tickLabelStyle = {
    fill: theme.palette.text.secondary,
    fontFamily: theme.typography.fontFamily,
    fontSize: 12
  };

  return (
    <>
      <Card sx={{ position: 'relative', '&:hover .panel-info-btn': { opacity: 1 } }}>
        <IconButton
          className="panel-info-btn"
          size="small"
          onClick={() => setOpen(true)}
          sx={{ position: 'absolute', top: 8, right: 8, opacity: 0, transition: 'opacity 0.2s' }}
        >
          <Info fontSize="small" />
        </IconButton>
        <Grid container direction="column" alignItems="center">
          <CardHeader title={caption} />
        </Grid>
        <Divider />
        <QueryValidationBadge errors={queryErrors} warnings={warnings} />

        <BarChart
          dataset={mungedRecords}
          xAxis={[{
            scaleType: 'band',
            dataKey: 'id',
            disableLine: true,
            disableTicks: true,
            tickLabelStyle
          }]}
          yAxis={[{
            disableLine: true,
            disableTicks: true,
            tickLabelStyle
          }]}
          series={[{
            dataKey: 'value',
            label: caption ?? 'Value'
          }]}
          borderRadius={6}
          colors={chartColorsFor(theme.palette.mode)}
          grid={{ horizontal: true }}
          hideLegend={!hasLegend}
          height={350}
          margin={
            barSettings?.legend === 'column'
              ? { top: 16, right: 150, bottom: 40, left: 48 }
              : barSettings?.legend === 'row'
                ? { top: 16, right: 16, bottom: 72, left: 48 }
                : { top: 16, right: 16, bottom: 40, left: 48 }
          }
          slotProps={hasLegend ? {
            legend: {
              position:
                barSettings?.legend === 'column'
                  ? { vertical: 'middle', horizontal: 'end' }
                  : { vertical: 'bottom', horizontal: 'center' },
              direction: barSettings?.legend === 'column' ? 'vertical' : 'horizontal'
            }
          } : undefined}
          sx={{
            '& .MuiChartsGrid-line': {
              stroke: theme.palette.divider,
              strokeDasharray: '4 4'
            }
          }}
        />
      </Card>
      <CypherDetails details={details} open={open} setOpen={setOpen} />
    </>
  );
}
