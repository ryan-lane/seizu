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
import { ResponsiveBar } from '@nivo/bar';
import CypherDetails from 'src/components/reports/CypherDetails';

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
  let margin = {
    top: 20,
    right: 20,
    bottom: 20,
    left: 60
  };

  if (barSettings?.legend === 'column') {
    margin = {
      top: 20,
      right: 80,
      bottom: 20,
      left: 60
    };
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
  } else if (barSettings?.legend === 'row') {
    margin = {
      top: 20,
      right: 20,
      bottom: 60,
      left: 60
    };
    legends.push({
      anchor: 'bottom',
      direction: 'row',
      justify: false,
      translateX: 0,
      translateY: 60,
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
          <ResponsiveBar
            data={mungedRecords}
            animate
            isInteractive
            margin={margin}
            theme={{
              text: { fill: theme.palette.text.primary },
              labels: { text: { fill: theme.palette.text.primary } },
              tooltip: {
                container: { background: theme.palette.background.paper }
              }
            }}
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
