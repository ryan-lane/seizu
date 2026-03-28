import { useEffect, useState } from 'react';
import {
  Card,
  CardContent,
  CardHeader,
  Divider,
  IconButton,
  Grid,
  Typography
} from '@mui/material';
import { useTheme } from '@mui/material/styles';
import Info from '@mui/icons-material/Info';
import Error from '@mui/icons-material/Error';
import { ThreeDots } from 'react-loader-spinner';
import { PieChart } from '@mui/x-charts/PieChart';
import { blueberryTwilightPalette } from '@mui/x-charts/colorPalettes';
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
    pieData.push({
      id: String(mungedData['id'] ?? i),
      value: Number(mungedData['value'] ?? 0),
      label: String(mungedData['id'] ?? i)
    });
  }

  const hasLegend = !!pieSettings?.legend;

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

        <PieChart
          series={[{
            data: pieData,
            // Donut style — looks cleaner with labels
            innerRadius: '35%',
            outerRadius: '80%',
            paddingAngle: 2,
            cornerRadius: 4,
            // Show arc labels only when no legend is configured
            arcLabel: hasLegend ? undefined : 'label',
            arcLabelMinAngle: 20,
            arcLabelRadius: '60%',
            highlightScope: { fade: 'global', highlight: 'item' },
            // faded.innerRadius only accepts number, not string
            faded: { additionalRadius: -4, color: theme.palette.action.disabled },
            valueFormatter: (item) => String(item.value)
          }]}
          colors={blueberryTwilightPalette}
          hideLegend={!hasLegend}
          height={350}
          margin={
            pieSettings?.legend === 'column'
              ? { top: 16, right: 160, bottom: 16, left: 16 }
              : pieSettings?.legend === 'row'
                ? { top: 16, right: 16, bottom: 80, left: 16 }
                : { top: 24, right: 24, bottom: 24, left: 24 }
          }
          slotProps={{
            ...(hasLegend && {
              legend: {
                position:
                  pieSettings?.legend === 'column'
                    ? { vertical: 'middle', horizontal: 'end' }
                    : { vertical: 'bottom', horizontal: 'center' },
                direction: pieSettings?.legend === 'column' ? 'vertical' : 'horizontal'
              }
            }),
            pieArcLabel: {
              style: {
                fontFamily: theme.typography.fontFamily ?? undefined,
                fontSize: 12,
                fontWeight: 500
              }
            }
          }}
        />
      </Card>
      <CypherDetails details={details} open={open} setOpen={setOpen} />
    </>
  );
}
