import { Helmet } from 'react-helmet';
import { Box, Container, Grid } from '@mui/material';
import Neo4jCredentials from '../components/Neo4j';

function Neo4j(props) {
  return (
    <>
      <Helmet>
        <title>Neo4j Browser | Seizu</title>
      </Helmet>
      <Box
        sx={{
          backgroundColor: 'background.default',
          minHeight: '100%',
          py: 3
        }}
      >
        <Container maxWidth={false}>
          <Grid container spacing={4}>
            <Grid item lg={12} md={12} xl={12} xs={12}>
              <Neo4jCredentials {...props} />
            </Grid>
          </Grid>
        </Container>
      </Box>
    </>
  );
}

export default Neo4j;
