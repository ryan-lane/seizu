import { useContext, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  Paper,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableRow,
  Tabs,
  Typography
} from '@mui/material';
import useMediaQuery from '@mui/material/useMediaQuery';
import { makeStyles, useTheme } from '@mui/styles';

import { ConfigContext } from 'src/config.context';
import CypherTable from 'src/components/reports/CypherTable';

const useStyles = makeStyles((theme) => ({
  button: {
    margin: theme.spacing(1)
  }
}));

function TabPanel(props) {
  const { children, value, index, ...other } = props;

  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`simple-tabpanel-${index}`}
      aria-labelledby={`simple-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ p: 3 }}>{children}</Box>}
    </div>
  );
}

TabPanel.propTypes = {
  children: PropTypes.node,
  index: PropTypes.number.isRequired,
  value: PropTypes.number.isRequired
};

function a11yProps(index) {
  return {
    id: `simple-tab-${index}`,
    'aria-controls': `simple-tabpanel-${index}`
  };
}

export default function CypherDetails({ details, open, setOpen }) {
  const { config } = useContext(ConfigContext);
  const theme = useTheme();
  const classes = useStyles();
  const fullScreen = useMediaQuery(theme.breakpoints.down('sm'));
  const handleClose = () => {
    setOpen(false);
  };

  const [value, setValue] = useState(0);
  const handleChange = (event, newValue) => {
    setValue(newValue);
  };

  let params;
  if (details.params !== undefined) {
    params = Object.keys(details.params).map((key) => {
      let paramKey = details.params[key];
      if (Array.isArray(details.params[key])) {
        paramKey = details.params[key].join(', ');
      }
      return (
        <div key={key}>
          {key}: {paramKey}
        </div>
      );
    });
  }

  let statsPrefix;
  if (config.stats.external_prefix === '') {
    statsPrefix = '';
  } else {
    statsPrefix = `${config.stats.external_prefix}.`;
  }

  let query;
  if (config.stats.external_provider === 'newrelic') {
    if (details.type === 'count') {
      let where;
      if (details.params === undefined || details.params.length === 0) {
        where = '';
      } else {
        where = `WHERE ${Object.keys(details.params)
          .map((key) => `${key} = '${details.params[key]}'`)
          .join(' ')}`;
      }
      query = `SELECT latest(\`${statsPrefix}${details.metric}.total.value\`) AS '${details.caption}' FROM Metric ${where} SINCE 24 HOURS AGO TIMESERIES AUTO`;
    } else if (details.type === 'progress') {
      let where;
      if (details.params === undefined || details.params.length === 0) {
        where = '';
      } else {
        where = `WHERE ${Object.keys(details.params)
          .map((key) => `${key} = '${details.params[key]}'`)
          .join(' ')}`;
      }
      query = `SELECT latest(\`${statsPrefix}${details.metric}.numerator.value\`) / latest(\`${statsPrefix}${details.metric}.denominator.value\`) * 100 AS '${details.caption}' FROM Metric ${where} SINCE 24 HOURS AGO TIMESERIES AUTO`;
    }
  }

  let cypherRow;
  if (details.cypher !== undefined && details.cypher !== null) {
    cypherRow = (
      <TableRow>
        <TableCell>
          <Typography variant="body">Cypher Query</Typography>
        </TableCell>
        <TableCell>
          <Typography variant="body" style={{ whiteSpace: 'pre-line' }}>
            {details.cypher}
          </Typography>
        </TableCell>
      </TableRow>
    );
  }

  let detailsCypherRow;
  if (details.details_cypher !== undefined && details.details_cypher !== null) {
    detailsCypherRow = (
      <TableRow>
        <TableCell>
          <Typography variant="body">Data Details Cypher Query</Typography>
        </TableCell>
        <TableCell>
          <Typography variant="body" style={{ whiteSpace: 'pre-line' }}>
            {details.details_cypher}
          </Typography>
        </TableCell>
      </TableRow>
    );
  }

  let paramsRow;
  if (params !== undefined && params.length !== 0) {
    paramsRow = (
      <TableRow>
        <TableCell>
          <Typography variant="body">
            Query Parameters (and statsd metric tags)
          </Typography>
        </TableCell>
        <TableCell>
          <Typography variant="body">{params}</Typography>
        </TableCell>
      </TableRow>
    );
  }

  let queryRow;
  if (query !== undefined) {
    queryRow = (
      <TableRow>
        <TableCell>
          <Typography variant="body">Example stats query</Typography>
        </TableCell>
        <TableCell>
          <Typography variant="body">{query}</Typography>
        </TableCell>
      </TableRow>
    );
  }

  let metricText;
  if (details.type === 'count') {
    metricText = (
      <Typography variant="body">
        {statsPrefix}
        {details.metric}
        .total
      </Typography>
    );
  } else if (details.type === 'progress') {
    metricText = (
      <>
        <Typography variant="body">
          {statsPrefix}
          {details.metric}
          .numerator
        </Typography>
        <br />
        <Typography variant="body">
          {statsPrefix}
          {details.metric}
          .denominator
        </Typography>
      </>
    );
  }
  let metricRow;
  if (details.metric !== undefined && details.metric !== null) {
    metricRow = (
      <>
        <TableRow>
          <TableCell>
            <Typography variant="body">Statsd metric</Typography>
          </TableCell>
          <TableCell>{metricText}</TableCell>
        </TableRow>
        {queryRow}
      </>
    );
  }
  let cypherTabs;
  let cypherTabPanel;
  if (details.details_cypher === undefined || details.details_cypher === null) {
    cypherTabs = [
      <Tab key={0} label="Query and Metric Details" {...a11yProps(0)} />
    ];
    cypherTabPanel = (
      <TabPanel value={value} index={0}>
        <TableContainer component={Paper}>
          <Table className={classes.table} aria-label="extra-details">
            <TableBody>
              {cypherRow}
              {detailsCypherRow}
              {paramsRow}
              {metricRow}
            </TableBody>
          </Table>
        </TableContainer>
      </TabPanel>
    );
  } else {
    cypherTabs = [
      <Tab key={0} label="Data Details" {...a11yProps(0)} />,
      <Tab key={1} label="Query and Metric Details" {...a11yProps(1)} />
    ];
    cypherTabPanel = (
      <>
        <TabPanel value={value} index={0}>
          <Typography gutterBottom variant="h4">
            Details for: {details.caption}
          </Typography>
          <CypherTable
            cypher={details.details_cypher}
            params={details.params}
            columns={details.columns}
            height="450px"
          />
        </TabPanel>
        <TabPanel value={value} index={1}>
          <TableContainer component={Paper}>
            <Table className={classes.table} aria-label="extra-details">
              <TableBody>
                {cypherRow}
                {detailsCypherRow}
                {paramsRow}
                {metricRow}
              </TableBody>
            </Table>
          </TableContainer>
        </TabPanel>
      </>
    );
  }

  return (
    <Dialog
      fullScreen={fullScreen}
      open={open}
      onClose={handleClose}
      aria-labelledby="responsive-dialog-title"
      maxWidth="xl"
      fullWidth
    >
      <DialogContent>
        <Box sx={{ width: '100%', height: '790px' }}>
          <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
            <Tabs
              value={value}
              onChange={handleChange}
              aria-label="Query and metric details tabs"
            >
              {cypherTabs}
            </Tabs>
          </Box>
          {cypherTabPanel}
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose} color="primary" autoFocus>
          Close
        </Button>
      </DialogActions>
    </Dialog>
  );
}

CypherDetails.propTypes = {
  details: PropTypes.object,
  open: PropTypes.bool,
  setOpen: PropTypes.func
};
