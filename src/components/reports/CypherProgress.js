import { useEffect, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Box,
  Card,
  CardContent,
  CardHeader,
  CircularProgress,
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

export default function CypherProgress({
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

  const numerator = neo4j.int(first.get('numerator')).toNumber();
  const denominator = neo4j.int(first.get('denominator')).toNumber();
  const percent = Math.floor((numerator / denominator) * 100);
  let circleColor = 'primary';
  let textColor = 'textPrimary';
  if (threshold === undefined) {
    if (percent < 70) {
      circleColor = 'error';
      textColor = 'error';
    } else if (percent === 100) {
      circleColor = 'success';
      textColor = 'success.main';
    }
  } else if (percent < threshold) {
    circleColor = 'error';
    textColor = 'error';
  } else if (percent === 100) {
    circleColor = 'success';
    textColor = 'success.main';
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
              <Typography variant="h3" component="span" color={textColor}>
                {numerator}
                <span> </span>
              </Typography>
              <Typography variant="h3" component="span">
                / {denominator}
              </Typography>
            </span>
          </CardContent>
          <CardContent>
            <Box sx={{ position: 'relative', display: 'inline-flex' }}>
              <CircularProgress
                variant="determinate"
                value={percent}
                color={circleColor}
                size={100}
              />
              <Box
                sx={{
                  top: 0,
                  left: 0,
                  bottom: 0,
                  right: 0,
                  position: 'absolute',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}
              >
                <Typography
                  variant="caption"
                  component="div"
                  color="text.secondary"
                >
                  {percent}%
                </Typography>
              </Box>
            </Box>
          </CardContent>
        </Grid>
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

CypherProgress.propTypes = {
  cypher: PropTypes.string,
  params: PropTypes.object,
  caption: PropTypes.string,
  threshold: PropTypes.number,
  details: PropTypes.object,
  needInputs: PropTypes.array
};
