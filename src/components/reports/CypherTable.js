import { useEffect, useState } from 'react';
import PropTypes from 'prop-types';
import { useLazyReadCypher } from 'use-neo4j';
import Error from '@mui/icons-material/Error';
import {
  Button,
  Dialog,
  DialogContent,
  DialogActions,
  IconButton,
  Tooltip,
  Typography
} from '@mui/material';
import MUIDataTable from 'mui-datatables';
import Info from '@mui/icons-material/Info';
import Fullscreen from '@mui/icons-material/Fullscreen';
import CloseFullscreen from '@mui/icons-material/CloseFullscreen';
// eslint-disable-next-line  import/no-extraneous-dependencies
import neo4j from 'neo4j-driver';

import CypherDetails from 'src/components/reports/CypherDetails';

export default function CypherTable({
  cypher,
  params,
  columns,
  caption,
  needInputs,
  details,
  height
}) {
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [expandOpen, setExpandOpen] = useState(false);
  const [expandSize, setExpandSize] = useState(window.innerHeight);
  const [runQuery, { loading, error, records, first }] =
    useLazyReadCypher(cypher);

  useEffect(() => {
    function handleResize() {
      setExpandSize(window.innerHeight);
    }

    window.addEventListener('resize', handleResize);
  }, []);

  useEffect(() => {
    if (needInputs === undefined || needInputs.length === 0) {
      runQuery(params);
    }
  }, [cypher, params]);

  if (needInputs !== undefined && needInputs.length > 0) {
    return (
      <div>
        <Typography variant="body2">
          Please set {needInputs.join(', ')}
        </Typography>
      </div>
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

  if (cypher === undefined) {
    return (
      <>
        <Error />
        <Typography variant="body2">Missing cypher query</Typography>
      </>
    );
  }

  const setOpenDetails = () => {
    setDetailsOpen(true);
  };

  const setOpenExpand = () => {
    setExpandOpen(true);
  };

  const setClosedExpand = () => {
    setExpandOpen(false);
  };

  const options = {
    responsive: 'simple',
    selectableRows: 'none',
    print: false,
    customToolbar: () => {
      const icons = [];
      if (details !== undefined) {
        icons.push(
          <Tooltip title="Show query details">
            <IconButton onClick={setOpenDetails}>
              <Info />
            </IconButton>
          </Tooltip>
        );
      }
      if (expandOpen === false) {
        icons.push(
          <Tooltip title="Fullscreen">
            <IconButton onClick={setOpenExpand}>
              <Fullscreen />
            </IconButton>
          </Tooltip>
        );
      } else {
        icons.push(
          <Tooltip title="Close Fullscreen">
            <IconButton onClick={setClosedExpand}>
              <CloseFullscreen />
            </IconButton>
          </Tooltip>
        );
      }
      return icons;
    }
  };

  if (expandOpen) {
    // window height minus the size of the table header and footer
    options.tableBodyHeight = `${expandSize - 225}px`;
    options.rowsPerPage = '100';
  } else if (height !== undefined) {
    options.tableBodyHeight = height;
  } else {
    // window height minus the size of the table header and footer, and the caption
    options.tableBodyHeight = `${expandSize - 275}px`;
    // Set the maximum height for normal views, to avoid expanding forever
    options.tableBodyMaxHeight = '750px';
  }

  if (loading || records === undefined) {
    return <MUIDataTable data={[]} columns={[]} options={{ options }} />;
  }

  if (records === null || records.length === 0) {
    return <Typography variant="body2">No records found.</Typography>;
  }

  if (first === undefined) {
    return <MUIDataTable data={[]} columns={[]} options={options} />;
  }

  let useDetails;
  const mungedColumns = [];
  if (columns === undefined) {
    useDetails = true;
    let columnKeys;
    let firstObject;
    try {
      firstObject = first.get('details');
      if (firstObject === null || firstObject === undefined) {
        return <MUIDataTable data={[]} columns={[]} options={options} />;
      }
      if (firstObject.properties === undefined) {
        columnKeys = Object.keys(firstObject);
      } else {
        columnKeys = Object.keys(firstObject.properties);
      }
    } catch (err) {
      console.log(err);
      return <Typography variant="body2">No records.</Typography>;
    }
    columnKeys.forEach((column) => {
      const columnData = {
        name: column,
        label: column
      };
      mungedColumns.push(columnData);
    });
  } else {
    useDetails = false;
    columns.forEach((column) => {
      const mungedColumn = column;
      mungedColumns.push(mungedColumn);
    });
  }

  const mungedRecords = [];
  for (let i = 0; i < records.length; i++) {
    const data = records[i];
    let mungedData;
    if (useDetails) {
      const dataDetails = data.get('details');
      if (dataDetails.properties === undefined) {
        mungedData = dataDetails;
      } else {
        mungedData = dataDetails.properties;
      }
    } else {
      mungedData = data.toObject();
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

  return (
    <>
      <Typography gutterBottom variant="h4">
        {caption}
      </Typography>
      <MUIDataTable
        data={mungedRecords}
        columns={mungedColumns}
        options={options}
      />
      {details !== undefined && (
        <CypherDetails
          details={details}
          open={detailsOpen}
          setOpen={setDetailsOpen}
        />
      )}
      <Dialog fullScreen open={expandOpen} onClose={setClosedExpand}>
        <DialogContent>
          <MUIDataTable
            data={mungedRecords}
            columns={mungedColumns}
            options={options}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={setClosedExpand} color="primary" autoFocus>
            Close
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}

CypherTable.propTypes = {
  cypher: PropTypes.string,
  params: PropTypes.object,
  columns: PropTypes.array,
  caption: PropTypes.string,
  needInputs: PropTypes.array,
  details: PropTypes.object,
  height: PropTypes.string
};
