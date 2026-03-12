/* eslint-disable no-underscore-dangle */
import React, { useState, useContext } from 'react';
import { Link } from '@mui/material';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableRow from '@mui/material/TableRow';
import Paper from '@mui/material/Paper';
import Snackbar from '@mui/material/Snackbar';
import ContentCopy from '@mui/icons-material/ContentCopy';
import Close from '@mui/icons-material/Close';
import OpenInNew from '@mui/icons-material/OpenInNew';
import Button from '@mui/material/Button';

import { ConfigContext } from 'src/config.context';

export default function Neo4jCredentials() {
  const { config, auth } = useContext(ConfigContext);
  const neo4jUrl = `${config.console_url}/browser/`;
  const [open, setOpen] = useState(false);

  const handleClick = () => {
    setOpen(true);
  };

  const handleClose = (event, reason) => {
    if (reason === 'clickaway') {
      return;
    }

    setOpen(false);
  };

  return (
    <>
      <TableContainer component={Paper}>
        <Table sx={{ maxWidth: 650 }} aria-label="credentials">
          <TableBody>
            <TableRow>
              <TableCell>Username</TableCell>
              <TableCell>{auth.username}</TableCell>
            </TableRow>
            <TableRow>
              <TableCell>Password</TableCell>
              <TableCell>
                <Button
                  variant="contained"
                  color="primary"
                  size="small"
                  sx={{ margin: 1 }}
                  endIcon={<ContentCopy />}
                  onClick={() => {
                    navigator.clipboard.writeText(auth.password);
                    handleClick();
                  }}
                >
                  Copy Password
                </Button>
              </TableCell>
            </TableRow>
            <TableRow>
              <TableCell>Neo4J Console</TableCell>
              <TableCell>
                <Link target="_blank" href={neo4jUrl}>
                  <p>
                    Open in a new tab <OpenInNew sx={{ fontSize: 16 }} />
                  </p>
                </Link>
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </TableContainer>
      <Snackbar
        anchorOrigin={{
          vertical: 'bottom',
          horizontal: 'center'
        }}
        open={open}
        autoHideDuration={6000}
        onClose={handleClose}
        message="Copied to clipboard"
        action={
          <Button
            size="small"
            aria-label="close"
            color="inherit"
            onClick={handleClose}
          >
            <Close />
          </Button>
        }
      />
    </>
  );
}
