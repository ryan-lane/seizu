# docker-compose

## Quickstart

A full docker-compose setup is included that can start neo4j, dynamodb, telegraph, seizu (and its workers), and can provide a quick way of running cartography to load your neo4j database with data.
Note that chrome will not allow you to use websockets without SSL when using localhost.
So, it's necessary to generate an SSL certificate that will be used by the docker-compose setup.

A script is included that will generate a CA and cert, and put it into your trust root:

```bash
$> make add_ssl

localhost certificate is missing; adding it...

Creating a minica CA, and a localhost certificate...

Add the minica CA to the system keychain trust:

  (OSX) sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain ~/.minica/minica.pem
  (Ubuntu) sudo cp ~/.minica/minica.pem /usr/local/share/ca-certificates/minica.crt; sudo update-ca-certificates

To remove the CA:

  (OSX) sudo security remove-trusted-cert -d ~/.minica/minica.pem
  (Ubuntu) sudo rm /usr/local/share/ca-certificates/minica.crt; sudo update-ca-certificates

$> sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain ~/.minica/minica.pem
Enter PIN for 'Certificate For PIV Authentication (Yubico PIV Authentication)':

```

After adding the SSL, you can start seizu using docker-compose:

```bash
$> export NEO4J_PASSWORD=<some_value>
$> make up -d
$> make logs seizu-node
```

Once fully started, the UI will be accessible at: https://localhost:8443/

The UI is also accessible directly through nodejs, which will recompile the UI on changes to the source.
This is useful for development.
This version of the UI is accessible at: https://localhost:8443/

### Loading CVE data

The quickstart configuration provided by the docker-compose is based around the NIST CVE data, which can be easily loaded via a make target:

```bash
$> make sync_cve
```

## Updating configuration

The ``up`` make target, prior to running docker-compose, copies a number of default configuration files into a git and docker ignored ``.compose`` directory. Once these initial files are copied in, they won't be overwritten or modified. If you need to change configuration for the docker-compose components, you can update them there. Specifically, if you're looking to update the dashboard configuration, that can be found at ``.compose/seizu/reporting-dashboard.yaml``.
