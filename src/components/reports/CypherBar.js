import { useEffect, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Card,
  CardContent,
  CardHeader,
  Divider,
  Button,
  Grid,
  Typography
} from '@mui/material';
import { useTheme } from '@mui/styles';
import Info from '@mui/icons-material/Info';
import Error from '@mui/icons-material/Error';
import Loader from 'react-loader-spinner';
import { useLazyReadCypher } from 'use-neo4j';
import { ResponsiveBar } from '@nivo/bar';
// eslint-disable-next-line  import/no-extraneous-dependencies
import neo4j from 'neo4j-driver';
import CypherDetails from 'src/components/reports/CypherDetails';

export default function CypherBar({
  cypher,
  params,
  caption,
  barSettings,
  details,
  needInputs
}) {
  const theme = useTheme();
  const [open, setOpen] = useState(false);
  const handleClickOpen = () => {
    setOpen(true);
  };

  const [runQuery, { loading, error, records, first }] =
    useLazyReadCypher(cypher);

  useEffect(() => {
    if (needInputs === undefined || needInputs.length === 0) {
      runQuery(params);
    }
  }, [cypher, params]);

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
    return <Loader type="ThreeDots" color="#2BAD60" height="50" width="50" />;
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
    let mungedData;
    const dataDetails = data.get('details');
    if (dataDetails.properties === undefined) {
      mungedData = dataDetails;
    } else {
      mungedData = dataDetails.properties;
    }
    Object.keys(mungedData).forEach((key) => {
      if (neo4j.isInt(mungedData[key])) {
        mungedData[key] = neo4j.int(mungedData[key]).toNumber();
      } else if (Array.isArray(mungedData[key])) {
        mungedData[key] = mungedData[key].join(', ');
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
              textColor: theme.palette.text.primary,
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
        params={params}
        open={open}
        setOpen={setOpen}
      />
    </>
  );
}

CypherBar.propTypes = {
  cypher: PropTypes.string,
  params: PropTypes.object,
  caption: PropTypes.string,
  barSettings: PropTypes.object,
  details: PropTypes.object,
  needInputs: PropTypes.array
};
