# Quickstart

A full docker-compose setup is included that can start neo4j, dynamodb, telegraf, seizu (and its workers), and can provide a quick way of running cartography to load your neo4j database with data.

First clone the seizu repo:

```bash
git clone https://github.com/mappedsky/seizu
cd seizu
```

Start the stack:

```bash
export NEO4J_PASSWORD=<some_value>
make up
make logs seizu-node
```

Once fully started, the UI will be accessible at: http://localhost:3000

The backend API is accessible at: http://localhost:8080

## Seeding reports

Report and dashboard configurations are stored in DynamoDB Local. After starting the stack for the first time, seed the example reports from the YAML config:

```bash
make seed_dashboard
```

This reads `.config/dev/seizu/reporting-dashboard.yaml`, creates each report in DynamoDB, and sets the dashboard pointer. After resetting the DynamoDB volume, re-run `make seed_dashboard` to repopulate.

To reset the database and reseed:

```bash
make drop_db
make up
make seed_dashboard
```

## Loading CVE data

The quickstart configuration provided by the docker-compose is based around the NIST CVE data, which can be easily loaded via a make target:

```bash
make sync_cve
```

## Testing authentication

The stack includes an embedded [Authentik](https://goauthentik.io/) OIDC provider. To enable it:

```bash
make auth_enable && make down && make up
```

On first run, Authentik takes about two minutes to initialize. Once ready, visit http://localhost:3000 and log in with:

- **Admin:** `akadmin` / `devpassword`
- **Developer:** `developer` / `devpassword`

To disable auth and return to the default unauthenticated mode:

```bash
make auth_disable && make down && make up
```
