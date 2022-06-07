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
import Info from '@mui/icons-material/Info';
import Error from '@mui/icons-material/Error';
import Loader from 'react-loader-spinner';
import { useLazyReadCypher } from 'use-neo4j';
// eslint-disable-next-line  import/no-extraneous-dependencies
import neo4j from 'neo4j-driver';
import CypherDetails from 'src/components/reports/CypherDetails';

export default function CypherCount({
  cypher,
  params,
  caption,
  threshold,
  details,
  needInputs
}) {
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
            <Typography variant="h4" align="center">
              N/A
            </Typography>
            <Typography variant="body2" align="center">
              (Set {needInputs.join(', ')})
            </Typography>
          </CardContent>
        </Grid>
      </Card>
    );
  }

  if (error) {
    console.log(error);
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

  const total = neo4j.int(first.get('total')).toNumber();
  let color;
  if (threshold === undefined) {
    color = 'textPrimary';
  } else if (total > threshold) {
    color = 'error';
  }

  return (
    <>
      <Card style={{ height: '100%' }}>
        <Grid container direction="column" alignItems="center">
          <CardHeader title={caption} />
        </Grid>
        <Divider />
        <Button size="small" color="inherit" onClick={handleClickOpen}>
          <Info />
        </Button>
        <Grid container spacing={0} direction="column" alignItems="center">
          <CardContent>
            <span>
              <Typography variant="h3" component="span" color={color}>
                {total}
              </Typography>
            </span>
          </CardContent>
        </Grid>
      </Card>
      <CypherDetails details={details} open={open} setOpen={setOpen} />
    </>
  );
}

CypherCount.propTypes = {
  cypher: PropTypes.string,
  params: PropTypes.object,
  caption: PropTypes.string,
  threshold: PropTypes.number,
  details: PropTypes.object,
  needInputs: PropTypes.array
};
