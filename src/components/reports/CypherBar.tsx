import { useEffect, useState } from 'react';
import {
  Card,
  CardContent,
  CardHeader,
  Divider,
  Button,
  Grid,
  Typography
} from '@mui/material';
import { useTheme } from '@mui/material/styles';
import Info from '@mui/icons-material/Info';
import Error from '@mui/icons-material/Error';
import { ThreeDots } from 'react-loader-spinner';
import { BarChart } from '@mui/x-charts/BarChart';
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
  const handleClickOpen = () => {
    setOpen(true);
  };

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
    return <ThreeDots color="#2BAD60" height="50" width="50" />;
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

  // Determine legend slot props based on barSettings
  type LegendPosition = {
    position?: { vertical: 'top' | 'middle' | 'bottom'; horizontal: 'start' | 'center' | 'end' };
    direction?: 'vertical' | 'horizontal';
    hidden?: boolean;
  };
  let legendProps: LegendPosition = { hidden: true };
  if (barSettings?.legend === 'column') {
    legendProps = {
      position: { vertical: 'middle', horizontal: 'end' },
      direction: 'vertical',
      hidden: false
    };
  } else if (barSettings?.legend === 'row') {
    legendProps = {
      position: { vertical: 'bottom', horizontal: 'center' },
      direction: 'horizontal',
      hidden: false
    };
  }

  return (
    <>
      <Card>
        <Grid container direction="column" alignItems="center">
          <CardHeader title={caption} />
        </Grid>
        <Divider />
        <Button size="small" color="inherit" onClick={handleClickOpen}>
          <Info />
        </Button>
        <QueryValidationBadge errors={queryErrors} warnings={warnings} />

        <BarChart
          dataset={mungedRecords}
          xAxis={[{
            scaleType: 'band',
            dataKey: 'id',
            tickLabelStyle: { fill: theme.palette.text.primary }
          }]}
          yAxis={[{
            tickLabelStyle: { fill: theme.palette.text.primary }
          }]}
          series={[{ dataKey: 'value', label: caption ?? 'Value' }]}
          height={350}
          margin={
            barSettings?.legend === 'column'
              ? { top: 20, right: 140, bottom: 40, left: 60 }
              : barSettings?.legend === 'row'
                ? { top: 20, right: 20, bottom: 80, left: 60 }
                : { top: 20, right: 20, bottom: 40, left: 60 }
          }
          slotProps={{ legend: legendProps }}
          sx={{
            '& .MuiChartsAxis-tickLabel': { fill: theme.palette.text.primary },
            '& .MuiChartsTooltip-root': { background: theme.palette.background.paper }
          }}
        />
      </Card>
      <CypherDetails
        details={details}
        open={open}
        setOpen={setOpen}
      />
    </>
  );
}
