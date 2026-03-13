import { Helmet } from 'react-helmet';
import { Box, Container, Typography } from '@mui/material';

function NotFound() {
  return (
    <>
      <Helmet>
        <title>404 | Seizu</title>
      </Helmet>
      <Box
        sx={{
          backgroundColor: 'background.default',
          display: 'flex',
          flexDirection: 'column',
          height: '100%',
          justifyContent: 'center'
        }}
      >
        <Container maxWidth="md">
          <Typography
            align="center"
            color="textPrimary"
            variant="h1"
            sx={{ mt: 4 }}
          >
            404: I think you are lost.
          </Typography>
          <Typography align="center" color="textPrimary" variant="subtitle2">
            Please use the navigation to find your way.
          </Typography>
          <Box sx={{ textAlign: 'center' }}>
            <img
              alt="Under development"
              src="/static/images/404.svg"
              style={{
                marginTop: 50,
                display: 'inline-block',
                maxWidth: '100%',
                width: 560
              }}
            />
          </Box>
        </Container>
      </Box>
    </>
  );
}

export default NotFound;
