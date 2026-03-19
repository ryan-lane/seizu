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
import { PieChart } from '@mui/x-charts/PieChart';
import { useLazyCypherQuery, QueryRecord } from 'src/hooks/useCypherQuery';
import CypherDetails from 'src/components/reports/CypherDetails';
import QueryValidationBadge from 'src/components/reports/QueryValidationBadge';

interface CypherPieProps {
  cypher?: string;
  params?: Record<string, unknown>;
  caption?: string;
  pieSettings?: { legend?: string };
  details?: Record<string, unknown>;
  needInputs?: string[];
}

export default function CypherPie({
  cypher,
  params,
  caption,
  pieSettings,
  details,
  needInputs
}: CypherPieProps) {
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

  const pieData: { id: string; value: number; label: string }[] = [];
  for (let i = 0; i < records.length; i++) {
    const data = records[i];
    let mungedData: Record<string, unknown>;
    const dataDetails = data['details'] as QueryRecord & { properties?: QueryRecord };
    if (dataDetails.properties === undefined) {
      mungedData = dataDetails;
    } else {
      mungedData = dataDetails.properties;
    }
    const idVal = String(mungedData['id'] ?? i);
    const numVal = Number(mungedData['value'] ?? 0);
    pieData.push({ id: idVal, value: numVal, label: idVal });
  }

  const hasLegend = pieSettings?.legend === 'column' || pieSettings?.legend === 'row';

  type LegendPosition = {
    position?: { vertical: 'top' | 'middle' | 'bottom'; horizontal: 'start' | 'center' | 'end' };
    direction?: 'vertical' | 'horizontal';
    hidden?: boolean;
  };
  let legendProps: LegendPosition = { hidden: true };
  if (pieSettings?.legend === 'column') {
    legendProps = {
      position: { vertical: 'middle', horizontal: 'end' },
      direction: 'vertical',
      hidden: false
    };
  } else if (pieSettings?.legend === 'row') {
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

        <PieChart
          series={[{
            data: pieData,
            arcLabel: hasLegend ? undefined : (item) => item.label,
            arcLabelMinAngle: 20,
            highlightScope: { fade: 'global', highlight: 'item' },
            valueFormatter: (item) => String(item.value)
          }]}
          height={350}
          margin={
            pieSettings?.legend === 'column'
              ? { top: 10, right: 160, bottom: 10, left: 10 }
              : pieSettings?.legend === 'row'
                ? { top: 10, right: 10, bottom: 80, left: 10 }
                : { top: 40, right: 80, bottom: 40, left: 80 }
          }
          slotProps={{ legend: legendProps }}
          sx={{
            '& .MuiChartsArcLabel-root': { fill: theme.palette.text.primary },
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
