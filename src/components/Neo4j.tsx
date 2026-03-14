import { useContext } from 'react';
import { Link } from '@mui/material';
import OpenInNew from '@mui/icons-material/OpenInNew';

import { ConfigContext } from 'src/config.context';

export default function Neo4jCredentials() {
  const { config } = useContext(ConfigContext);
  const neo4jUrl = `${config.console_url}/browser/`;

  return (
    <Link target="_blank" href={neo4jUrl}>
      Open Neo4j Browser <OpenInNew sx={{ fontSize: 16 }} />
    </Link>
  );
}
