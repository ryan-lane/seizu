import { useState } from 'react';
import PropTypes from 'prop-types';
import Button from '@mui/material/Button';
import AccountCircle from '@mui/icons-material/AccountCircle';
import Box from '@mui/material/Box';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogContentText from '@mui/material/DialogContentText';
import DialogTitle from '@mui/material/DialogTitle';
import Lock from '@mui/icons-material/Lock';
import Password from '@mui/icons-material/Password';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';

import { createDriver } from 'use-neo4j';

export default function AuthDialog({ setAuth, neo4jSettings, setDriver }) {
  const [username, setUsername] = useState();
  const [password, setPassword] = useState();
  const [authenticating, setAuthenticating] = useState(true);
  const [error, setError] = useState();

  const handleUsernameChange = (event) => {
    setUsername(event.target.value);
  };

  const handlePasswordChange = (event) => {
    setPassword(event.target.value);
  };

  const handleSubmit = () => {
    setAuth({
      username,
      password
    });
    const d = createDriver(
      neo4jSettings.protocol,
      neo4jSettings.hostname,
      neo4jSettings.port,
      username,
      password
    );
    d.verifyConnectivity()
      .then(() => {
        setDriver(d);
        setAuthenticating(false);
      })
      .catch((e) => setError(e));
  };

  const handleKeyPress = (event) => {
    // Submit on enter keypress, which is code 13
    if (event.keyCode === 13) {
      handleSubmit();
    }
  };

  return (
    <Dialog open={authenticating}>
      <DialogTitle>Log into Neo4j</DialogTitle>
      <DialogContent>
        {error && (
          <DialogContentText color="error.main">
            Authentication failed. Please check your username/password and try
            again.
          </DialogContentText>
        )}
        <Box sx={{ display: 'flex', alignItems: 'flex-end' }}>
          <AccountCircle sx={{ color: 'action.active', mr: 1, my: 0.5 }} />
          <TextField
            required
            margin="dense"
            id="username-input"
            label="Username"
            onChange={handleUsernameChange}
            onKeyDown={handleKeyPress}
          />
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'flex-end' }}>
          <Password sx={{ color: 'action.active', mr: 1, my: 0.5 }} />
          <TextField
            required
            margin="dense"
            id="password-input"
            label="Password"
            type="password"
            onChange={handlePasswordChange}
            onKeyDown={handleKeyPress}
          />
        </Box>
      </DialogContent>
      <DialogActions>
        <Stack direction="row" spacing={2}>
          <Button variant="contained" endIcon={<Lock />} onClick={handleSubmit}>
            Submit
          </Button>
        </Stack>
      </DialogActions>
    </Dialog>
  );
}

AuthDialog.propTypes = {
  setAuth: PropTypes.func.isRequired,
  neo4jSettings: PropTypes.object.isRequired,
  setDriver: PropTypes.func.isRequired
};
