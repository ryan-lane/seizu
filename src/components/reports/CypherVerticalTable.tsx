import { useEffect, useState } from 'react';
import {
  Button,
  Divider,
  List,
  ListItem,
  Paper,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableRow
} from '@mui/material';
import Info from '@mui/icons-material/Info';
import Error from '@mui/icons-material/Error';
import { ThreeDots } from 'react-loader-spinner';

import { useLazyCypherQuery, QueryRecord } from 'src/hooks/useCypherQuery';
import CypherDetails from 'src/components/reports/CypherDetails';

interface CypherVerticalTableProps {
  cypher?: string;
  params?: Record<string, unknown>;
  id?: string;
  details?: Record<string, unknown>;
  needInputs?: string[];
}

export default function CypherVerticalTable({
  cypher,
  params,
  id,
  details,
  needInputs
}: CypherVerticalTableProps) {
  const [open, setOpen] = useState(false);
  const handleClickOpen = () => {
    setOpen(true);
  };

  const [runQuery, { loading, error, records }] = useLazyCypherQuery(cypher);

  useEffect(() => {
    if (needInputs === undefined || needInputs.length === 0) {
      runQuery(params);
    }
  }, [cypher, params, runQuery]);

  if (cypher === undefined) {
    return (
      <>
        <Error />
        <Typography variant="body2">Missing cypher query</Typography>
      </>
    );
  }

  if (needInputs !== undefined && needInputs.length > 0) {
    return (
      <div style={{ height: 400, width: '100%' }}>
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

  if (loading || records === undefined) {
    return <ThreeDots color="#2BAD60" height="50" width="50" />;
  }

  if (records === null || records.length === 0) {
    return <Typography variant="body2">No records found.</Typography>;
  }

  function makeTable(data: Record<string, unknown>) {
    const rows = [];
    Object.keys(data).forEach((key) => {
      const cells = [];
      let cellData;
      if (data[key] === undefined || data[key] === null) {
        // return here is inside the forEach, so it's effectively a continue
        return;
      }
      if (Array.isArray(data[key])) {
        // Unique the list prior to iterating over it.
        const uniqueItems = [...new Set(data[key] as unknown[])];
        const listItems = [];
        uniqueItems.forEach((item, index) => {
          let mungedItem;
          if (typeof item === 'object' && item !== null) {
            mungedItem = makeTable(item as Record<string, unknown>);
          } else {
            mungedItem = String(item);
          }
          listItems.push(
            // eslint-disable-next-line  react/no-array-index-key
            <ListItem disableGutters key={`${key}-${index}`}>
              {mungedItem}
            </ListItem>
          );
          if (uniqueItems.length !== 1) {
            listItems.push(
              // eslint-disable-next-line  react/no-array-index-key
              <Divider key={`${key}-${index}-divider`} component="li" />
            );
          }
        });
        cellData = (
          <List disablePadding dense sx={{ mt: -0.5 }}>
            {listItems}
          </List>
        );
      } else if (typeof data[key] === 'object') {
        cellData = makeTable(data[key] as Record<string, unknown>);
      } else {
        const item = data[key];
        cellData = <Typography variant="body1">{String(item)}</Typography>;
      }
      cells.push(
        <TableCell
          width="250px"
          style={{ borderBottom: 'none', verticalAlign: 'top' }}
          key={key}
        >
          {key}
        </TableCell>
      );
      cells.push(
        <TableCell
          width="100%"
          style={{ borderBottom: 'none', verticalAlign: 'top' }}
          key={`${key}-data`}
        >
          {cellData}
        </TableCell>
      );
      rows.push(
        <TableRow style={{ borderTop: '1px' }} key={key}>
          {cells}
        </TableRow>
      );
    });
    return (
      <Table sx={{ maxWidth: '100%', m: -0.7, ml: -1.9 }} size="small">
        <TableBody>{rows}</TableBody>
      </Table>
    );
  }

  const tables = [];
  for (let i = 0; i < records.length; i++) {
    let mungedData: Record<string, unknown>;
    const record = records[i];
    const dataDetails = record['details'] as QueryRecord & { properties?: QueryRecord };
    if (dataDetails.properties === undefined) {
      mungedData = dataDetails;
    } else {
      mungedData = dataDetails.properties;
    }
    const caption = String(mungedData[id]);
    const table = makeTable(mungedData);
    tables.push(
      <div key={i}>
        <Typography gutterBottom variant="h4">
          {caption}
          <Button
            variant="text"
            size="small"
            color="inherit"
            onClick={handleClickOpen}
            sx={{ mt: -0.5 }}
          >
            <Info fontSize="small" />
          </Button>
        </Typography>
        <Divider />
        <TableContainer component={Paper} sx={{ p: 2 }}>
          {table}
        </TableContainer>
      </div>
    );
  }

  return (
    <>
      {tables}
      <CypherDetails details={details} open={open} setOpen={setOpen} />
    </>
  );
}
