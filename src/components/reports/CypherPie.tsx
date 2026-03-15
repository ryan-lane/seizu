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
import { useLazyCypherQuery, QueryRecord } from 'src/hooks/useCypherQuery';
import { ResponsivePie } from '@nivo/pie';
import CypherDetails from 'src/components/reports/CypherDetails';

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

  const [runQuery, { loading, error, records, first }] =
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

  const mungedRecords = [];
  for (let i = 0; i < records.length; i++) {
    const data = records[i];
    let mungedData: Record<string, unknown>;
    const dataDetails = data['details'] as QueryRecord & { properties?: QueryRecord };
    if (dataDetails.properties === undefined) {
      mungedData = dataDetails;
    } else {
      mungedData = dataDetails.properties;
    }
    Object.keys(mungedData).forEach((key) => {
      if (Array.isArray(mungedData[key])) {
        mungedData[key] = (mungedData[key] as unknown[]).join(', ');
      }
    });
    mungedRecords.push(mungedData);
  }

  const legends = [];
  let enableArcLinkLabels = true;
  let margin = {
    top: 40,
    right: 80,
    bottom: 40,
    left: 80
  };

  if (pieSettings?.legend === 'column') {
    margin = {
      top: 10,
      right: 120,
      bottom: 10,
      left: 20
    };
    enableArcLinkLabels = false;
    legends.push({
      anchor: 'top-right',
      direction: 'column',
      justify: false,
      translateX: 120,
      translateY: 0,
      itemWidth: 100,
      itemHeight: 20,
      itemsSpacing: 0,
      symbolSize: 20,
      itemDirection: 'left-to-right'
    });
  } else if (pieSettings?.legend === 'row') {
    margin = {
      top: 10,
      right: 40,
      bottom: 40,
      left: 40
    };
    enableArcLinkLabels = false;
    legends.push({
      anchor: 'bottom',
      direction: 'row',
      justify: false,
      translateX: 0,
      translateY: 40,
      itemWidth: 80,
      itemHeight: 20,
      itemsSpacing: 10,
      symbolSize: 20,
      itemDirection: 'left-to-right'
    });
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

        <div style={{ height: 350 }}>
          <ResponsivePie
            data={mungedRecords}
            animate
            isInteractive
            activeOuterRadiusOffset={8}
            margin={margin}
            enableArcLinkLabels={enableArcLinkLabels}
            arcLabelsRadiusOffset={0.7}
            theme={{
              text: { fill: theme.palette.text.primary },
              labels: { text: { fill: theme.palette.text.primary } },
              tooltip: {
                container: { background: theme.palette.background.paper }
              }
            }}
            arcLabelsTextColor={{ from: theme.palette.text.secondary }}
            sortByValue
            legends={legends}
          />
        </div>
      </Card>
      <CypherDetails
        details={details}
        open={open}
        setOpen={setOpen}
      />
    </>
  );
}
