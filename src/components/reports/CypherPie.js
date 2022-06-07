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
import { ResponsivePie } from '@nivo/pie';
// eslint-disable-next-line  import/no-extraneous-dependencies
import neo4j from 'neo4j-driver';
import CypherDetails from 'src/components/reports/CypherDetails';

export default function CypherPie({
  cypher,
  params,
  caption,
  pieSettings,
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

CypherPie.propTypes = {
  cypher: PropTypes.string,
  params: PropTypes.object,
  caption: PropTypes.string,
  pieSettings: PropTypes.string,
  details: PropTypes.object,
  needInputs: PropTypes.array
};
