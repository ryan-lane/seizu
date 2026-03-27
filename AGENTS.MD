# Agent Guidelines

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is Seizu?

Seizu (星図) is a configuration-driven reporting platform for Neo4j graph data. Three runtimes:
- **FastAPI web app** (`reporting/`) — serves the React frontend and REST API (ASGI, Gunicorn + UvicornWorker)
- **Scheduled query worker** (`reporting/scheduled_queries.py`) — runs Cypher queries on a schedule with pluggable action plugins (SQS, Slack, log); reads from the database, not the YAML config
- **Dashboard stats worker** (`reporting/dashboard_stats.py`) — pushes panel metrics into StatsD/Telegraf

## Running Commands with Docker

Never install bun, node, pipenv, or Python directly on the host. Always use `docker compose run --rm <service>`.

### Frontend (`seizu-node`)

```bash
docker compose run --rm seizu-node bun add <package>          # install
docker compose run --rm seizu-node bun test --watchAll=false   # all tests
docker compose run --rm seizu-node bun test src/path/to.test.tsx --watchAll=false
docker compose run --rm seizu-node bun run type-check
```

### Backend (`seizu`)

```bash
docker compose run --rm seizu bash -c "pipenv sync --dev && pipenv run pytest tests/unit"
docker compose run --rm seizu bash -c "pipenv sync --dev && pipenv run pytest tests/unit/path/test.py::test_name"
docker compose run --rm seizu pipenv install <package>
```

> **Always `pipenv sync --dev` before pytest** — the `.venv` is project-dir-persisted and may be stale after new packages are added.
> **After editing `Pipfile`**, run `docker compose run --rm seizu pipenv lock` then `make lock` to regenerate `requirements.txt`. Commit both `Pipfile` and `Pipfile.lock` together.

### Linting

Run pre-commit **on the host** (the `seizu` container lacks git):
```bash
pre-commit run --all-files
make lint   # same thing
```

### Makefile shortcuts

```bash
make test / make test_unit / make test_frontend
make lint
make schema             # regenerate schema/reporting-schema.json and schema/openapi.json
make generate_openapi   # export schema/openapi.json (no running server needed)
make generate_client LANG=go  # generate client from schema/openapi.json
make seed_dashboard [ARGS="--force|--dry-run|export"]
make auth_enable / make auth_disable
make sqlmodel_enable / make sqlmodel_disable
```

## Adjacent Services Configuration

Config for adjacent dev services lives in `.config/`. Reference that path in `docker-compose.yml`.

`.config/setup.sh` (called by `make up`) copies `.config/dev/` → `.compose/` **only if the destination doesn't exist**. To apply a change to a source file, manually copy it or delete the destination and re-run `make up`. New env vars go in `.env.example`.

**Gunicorn** socket/PID/workdir are set to `/run/seizu` (ephemeral tmpfs) to avoid `EINVAL` errors on macOS Docker bind mounts.

## Architecture

### Frontend (`src/`)

React 19 + TypeScript + Bun + Material-UI + MUI X Charts + `@xyflow/react`.

**Key files:**
- `src/config.context.ts` — `ConfigContext` from `GET /api/v1/config`; OIDC + stats config; Cypher query resolution is per-report via `Report.queries`
- `src/authConfig.context.ts` — `AuthConfigContext`; holds `auth_required`; gates API calls until a token is present
- `src/auth.context.ts` — `AuthContext`; OIDC `user` + `accessToken`
- `src/userManager.ts` — `oidc-client-ts` `UserManager` singleton; returns `null` when auth is off
- `src/components/AuthProvider.tsx` — OIDC flow; registers events, calls `getUser()`, triggers `signinRedirect()` when unauthenticated
- `src/components/OidcCallback.tsx` — `/auth/callback`; calls `signinRedirectCallback()` then navigates to `/`
- `src/hooks/useCypherQuery.ts` — wraps `POST /api/v1/query`; skips if `auth_required` and no token
- `src/hooks/useReportsApi.ts` — `useReportsList()`, `useReport(id)`, `useDashboardReport()`, `useAllReports()`, `useReportVersionsList(id)`, `useReportVersion(id, v)`; `useReportsMutations()` for create/save-version/set-dashboard/delete
- `src/components/ReportView.tsx` — shared report renderer; resolves panel `cypher` against `report.queries`
- `src/components/reports/` — panel components (`CypherCount`, `CypherTable`, `CypherBar`, etc.)
- `src/components/reports/CypherGraph.tsx` — graph panel (`@xyflow/react`); accepts map, path, or any format; Graph/Table/Raw tabs; collapsible detail panel
- `src/pages/QueryConsole.tsx` — ad-hoc console at `/app/query-console`; Ctrl+Enter runs query
- `src/components/QueryConsoleSchemaPanel.tsx` — collapsible schema browser; inserts/runs discovery queries on click
- All POST requests must include `X-CSRFToken` header

**User identity:**
- `src/hooks/useCurrentUser.ts` — `useCurrentUser()` → `GET /api/v1/me`
- `src/hooks/useUser.ts` — `useUser(userId)` → `GET /api/v1/users/<userId>`
- `src/components/UserAvatar.tsx` — `boring-avatars` pixel avatar; use `<UserAvatar name={...} />`
- `src/components/UserDisplay.tsx` — resolves `created_by` user_id to `display_name ?? email`; use `<UserDisplay userId={...} />`
- **Never** display raw user_ids or `sub` values in the UI.

### Backend (`reporting/`)

FastAPI, Python 3.12, Gunicorn + UvicornWorker (ASGI). All I/O is async (neo4j async driver, aioboto3, async SQLAlchemy).

**Key files:**
- `reporting/asgi.py` — ASGI entrypoint: `application = create_app()`
- `reporting/app.py` — `create_app()`; FastAPI with `openapi_url="/api/openapi.json"`, `docs_url="/api/docs"`; registers security headers (`secure`), CSRF (`starlette-csrf`), routers, static files, and SPA fallback via `lifespan`
- `reporting/settings.py` — all config via env vars (Pydantic)
- `reporting/routes/` — `APIRouter`s: `config.py`, `me.py`, `query.py`, `reports.py`, `users.py`, `validate.py`, `scheduled_queries.py`, `static.py` (healthcheck only)
- `reporting/authnz/__init__.py` — `HTTPBearer` + FastAPI `Depends(get_current_user)`; `CurrentUser` dataclass (`user: User`, `jwt_claims: dict`); `sync_user_profile` dependency chains on `get_current_user`; tests override via `app.dependency_overrides[get_current_user]`
- `reporting/services/` — all async: `reporting_neo4j.py` (async Neo4j driver + distributed locking), `report_store/` (pluggable store), `query_validator.py`, `reporting_statsd.py`
- `reporting/schema/reporting_config.py` — Pydantic models for the YAML config
- `reporting/schema/report_config.py` — Pydantic models for DynamoDB items and API schemas

**Async I/O notes:**
- Neo4j: `AsyncGraphDatabase.driver()` for app/worker; a separate `GraphDatabase.driver()` is kept only for CyVer validators (run via `asyncio.to_thread`)
- DynamoDB/SQS: `aioboto3.Session().resource(...)` / `.client(...)` as async context managers
- PostgreSQL: `create_async_engine(...)` + `AsyncSession` from `sqlalchemy.ext.asyncio`; URL prefix `postgresql+asyncpg://`

**Query validation** (`reporting/services/query_validator.py`): `async def validate_query()` returns `ValidationResult(errors, warnings)`. Errors block execution; warnings don't.
1. Syntax + read-only check via `EXPLAIN` (async Neo4j driver)
2. SSRF/exfiltration guard (regex)
3. Schema warnings (CyVer `SchemaValidator` via `asyncio.to_thread` with sync driver)
4. Property warnings (CyVer `PropertiesValidator` via `asyncio.to_thread` with sync driver)

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/config` | OIDC config, stats config, JSON schema |
| POST | `/api/v1/query` | Execute validated read-only Cypher; returns `{results, errors, warnings}` |
| POST | `/api/v1/validate` | Validate Cypher without executing; returns `{errors, warnings}` |
| GET | `/api/v1/reports` | List reports (metadata only) |
| POST | `/api/v1/reports` | Create report; 201 |
| GET | `/api/v1/reports/dashboard` | Latest dashboard report; 404 if none |
| PUT | `/api/v1/reports/<id>/dashboard` | Set default dashboard |
| GET | `/api/v1/reports/<id>` | Latest version of a report |
| GET | `/api/v1/reports/<id>/versions` | All versions |
| GET | `/api/v1/reports/<id>/versions/<n>` | Specific version |
| POST | `/api/v1/reports/<id>/versions` | Save new version; 201 |
| DELETE | `/api/v1/reports/<id>` | Delete report + all versions |
| GET | `/api/v1/me` | Current user profile |
| GET | `/api/v1/users/<user_id>` | User profile by ID; 404 if not found |
| GET/POST | `/api/v1/scheduled-queries` | List / create |
| GET/PUT/DELETE | `/api/v1/scheduled-queries/<id>` | Get / update / delete |
| GET | `/api/v1/scheduled-queries/<id>/versions` | All versions |
| GET | `/api/v1/scheduled-queries/<id>/versions/<n>` | Specific version |
| GET/POST | `/api/v1/toolsets` | List / create toolsets |
| GET/PUT/DELETE | `/api/v1/toolsets/<id>` | Get / update / delete toolset |
| GET | `/api/v1/toolsets/<id>/versions` | All toolset versions |
| GET | `/api/v1/toolsets/<id>/versions/<n>` | Specific toolset version |
| GET/POST | `/api/v1/toolsets/<id>/tools` | List / create tools |
| GET/PUT/DELETE | `/api/v1/toolsets/<id>/tools/<tool_id>` | Get / update / delete tool |
| GET | `/api/v1/toolsets/<id>/tools/<tool_id>/versions` | All tool versions |
| GET | `/api/v1/toolsets/<id>/tools/<tool_id>/versions/<n>` | Specific tool version |
| GET | `/healthcheck` | Healthcheck |
| GET | `/api/openapi.json` | OpenAPI 3.x spec |
| GET | `/api/docs` | Swagger UI |

### CLI (`seizu_cli/`)

Typer app calling the REST API. Invoked via `python -m seizu_cli`.

**Key files:**
- `seizu_cli/main.py` — entry point; global options `--api-url`, `--token`, `--credentials-file`, `--config-file`
- `seizu_cli/config.py` — `SeizuConfig` + `load_config()` reading `~/.config/seizu/seizu.conf`
- `seizu_cli/client.py` — `SeizuClient`; Bearer auth + CSRF bootstrapping (calls `GET /api/v1/config` first)
- `seizu_cli/state.py` — module-level state; `get_client()` lazy factory
- `seizu_cli/commands/` — `reports.py`, `scheduled_queries.py`, `seed.py`, `auth.py`
- `seizu_cli/auth.py` — OS-native keyring or `--credentials-file` fallback; Device Authorization Grant

**Config file** (`~/.config/seizu/seizu.conf`): `api_url` and `seed_file`. Resolution: CLI flag → env var → conf file → default.

**Auth (Device Authorization Grant, RFC 8628):** `seizu login` → device endpoint → user approves in browser → CLI polls → token stored in keyring.

**Usage (inside `seizu` container):**
```bash
PYTHONPATH=/home/seizu/seizu pipenv run python -m seizu_cli --api-url http://seizu:8080 login
PYTHONPATH=/home/seizu/seizu pipenv run python -m seizu_cli --api-url http://seizu:8080 reports list
PYTHONPATH=/home/seizu/seizu pipenv run python -m seizu_cli --api-url http://seizu:8080 seed [--force|--dry-run]
PYTHONPATH=/home/seizu/seizu pipenv run python -m seizu_cli --api-url http://seizu:8080 export
```
Prefer `make seed_dashboard [ARGS="--force|--dry-run|export"]`.

### MCP Server (`reporting/services/mcp_server.py`)

Seizu exposes an MCP (Model Context Protocol) server at `/api/v1/mcp` when `MCP_ENABLED=true` (default). LLM agents such as Claude can connect and call tools as a standard MCP client.

**Key details:**
- Transport: StreamableHTTP, mounted as a Starlette ASGI sub-app inside FastAPI via `app.mount()`
- Auth: `_MCPAuthMiddleware` validates Bearer JWT tokens using the same `PyJWKClient` logic as the REST API; passes through unauthenticated in dev (`DEVELOPMENT_ONLY_REQUIRE_AUTH=false`)
- CSRF: exempt — MCP clients are not browsers and do not use cookie-based auth
- Tool names: namespaced as `{toolset_name}__{tool_name}` (double underscore)
- Tool listing: `@server.list_tools()` queries `report_store.list_enabled_tools()` at request time (dynamic, not static)
- Tool execution: `@server.call_tool()` runs the tool's Cypher query via `reporting_neo4j.run_query()`

**Built-in tool:** `seizu__schema` — always available; runs `CALL db.labels()`, `CALL db.relationshipTypes()`, `CALL db.propertyKeys()` and returns the graph schema.

**OAuth metadata endpoint:** `GET /api/v1/mcp/.well-known/oauth-authorization-server` (RFC 8414). Enabled when `MCP_OAUTH_AUTHORIZATION_ENDPOINT` and `MCP_OAUTH_TOKEN_ENDPOINT` are set. Allows MCP clients (e.g. Claude Desktop) to discover the OIDC provider and authenticate users without a pre-issued token. The auth middleware passes `.well-known` requests through unauthenticated. Settings: `MCP_OAUTH_ISSUER`, `MCP_OAUTH_AUTHORIZATION_ENDPOINT`, `MCP_OAUTH_TOKEN_ENDPOINT`.

**Toolsets and Tools** are user-managed groupings of Cypher-backed tools, stored in the same report store backend (DynamoDB or SQL) with full version history. CRUD is via the REST API. Cypher is validated at create/update time — write queries are blocked.

**DynamoDB key space:**
```
TOOLSET#{id} / #METADATA, VERSION#NNNNNNNNNN
TOOLSET_LIST / TOOLSET#{id}
TOOL#{id}    / #METADATA, VERSION#NNNNNNNNNN
TOOL_LIST#{toolset_id} / TOOL#{id}
```

**SQL tables:** `toolsets`, `toolset_versions`, `tools`, `tool_versions`

### Configuration System

Reports and scheduled queries are stored in DynamoDB (default) or PostgreSQL (`sqlmodel` backend). The YAML config (`.config/dev/seizu/reporting-dashboard.yaml`, mounted as `/reporting-dashboard.yaml`) is a seed source.

**YAML top-level sections:**
- `queries` — named Cypher strings for `scheduled_queries` references only; not served to frontend
- `dashboard` — key pointing to the default dashboard report
- `reports` — report definitions to seed into DynamoDB; each has its own `queries` dict
- `scheduled_queries` — **list** of recurring query definitions (SQS, Slack, log actions)

**Report storage** (`reporting/services/report_store/`):
- `base.py` — `ReportStore` ABC
- `dynamodb.py` — single-table design; composite PK/SK; Snowflake IDs; `SNOWFLAKE_MACHINE_ID`
- `sql.py` — SQLModel/SQLAlchemy; 5 tables; configured via `SQL_DATABASE_URL`
- `__init__.py` — `get_store()` factory (env `REPORT_STORE_BACKEND`, default `dynamodb`)

Use `from reporting.services import report_store` — backend is transparent.

**Switching backends:** `make sqlmodel_enable / sqlmodel_disable` then `make down && make up`.

**DynamoDB key design:** `#METADATA`, `#LATEST`, `VERSION#<n>` per report; `SQ#<id>` + `SCHEDULED_QUERY_LIST` per scheduled query; `#DASHBOARD/#POINTER` for the default dashboard.

**Seeding:** Existing reports/queries unchanged unless content differs or `--force`. `cypher` fields resolved against top-level `queries` dict, falling back to literal string. The `Report` TypeScript interface in `src/config.context.ts` must stay in sync with the Pydantic `Report` in `reporting/schema/reporting_config.py`.

### Cartography Data Sync

`nostart` profile. Entrypoint is already `cartography` — do not prefix with it.

```bash
make sync_cve / sync_aws / sync_github / sync_crowdstrike / sync_k8s
```

### Scheduled Query Action Plugins

Located in `reporting/scheduled_query_modules/`. Implement `ModuleInterface` from `__init__.py`.

Required methods: `action_name()`, `setup()`, `handle_results(scheduled_query_id, action, results)`, `action_config_schema()` → `List[ActionConfigFieldDef]` (types: `string`, `text`, `number`, `boolean`, `string_list`, `select`).

Action schemas served via `GET /api/v1/config` as `scheduled_query_action_schemas`.

### Docker Services

| Service | Role |
|---------|------|
| `seizu` | FastAPI backend + static frontend |
| `seizu-node` | Bun dev server |
| `seizu-dashboard-stats` | Stats worker |
| `seizu-scheduled-queries` | Scheduled query worker |
| `neo4j` | Graph database |
| `dynamodb` | DynamoDB Local (default backend) |
| `postgres` | PostgreSQL (`sqlmodel` profile) |
| `telegraf` | Metrics aggregation |
| `sqs` | ElasticMQ (local SQS) |
| `authentik-*` | OIDC provider (profile: `auth`) |
| `cartography` | Graph data sync (profile: `nostart`) |

Dev URLs: frontend `http://localhost:3000`, backend `http://localhost:8080`, Authentik `http://localhost:9000`.

**Reset named volumes:**
```bash
docker compose down
docker volume rm seizu_neo4j_data seizu_dynamodb_data
docker compose up && make seed_dashboard
```

### Authentication

Backend validates JWTs via `PyJWKClient` (PyJWT) against any OIDC JWKS endpoint.

| Env var | Default | Notes |
|---------|---------|-------|
| `JWKS_URL` | `""` | JWKS endpoint |
| `JWT_EMAIL_CLAIM` | `email` | JWT claim for email |
| `JWT_ISSUER` | `""` | Optional issuer check |
| `JWT_AUDIENCE` | `""` | Must match OIDC client ID when using Authentik |
| `DEVELOPMENT_ONLY_REQUIRE_AUTH` | `true` | Set `false` to bypass auth in dev |
| `TALISMAN_FORCE_HTTPS` | `true` | Set `false` in dev/behind LB |
| `SESSION_COOKIE_SECURE` | `true` | Must match `TALISMAN_FORCE_HTTPS`; if mismatched, CLI gets 403 on CSRF |
| `CSRF_COOKIE_SECURE` | `true` | Set `false` in dev |
| `OIDC_AUTHORITY` | `""` | Served to frontend via `/api/v1/config` |
| `OIDC_CLIENT_ID` | `""` | Served to frontend |
| `OIDC_SCOPE` | `"openid email"` | Served to frontend |

Frontend PKCE flow is driven entirely by runtime config from `GET /api/v1/config` — no build-time `REACT_APP_OIDC_*` vars. `redirect_uri` is always derived from `window.location.origin`.

**Local Authentik setup:**
```bash
make auth_enable && make down && make up   # enable; first run ~2 min
# visit http://localhost:3000, log in as developer/devpassword
make auth_disable && make down && make up  # revert
```
Setup is fully automated via `.config/dev/authentik/blueprints/seizu.yaml`. Device code flow requires `flow_device_code` set on the **Brand** (not the OAuth2Provider). Registered redirect URIs: `http://localhost:3000/auth/callback` and `http://localhost:8080/auth/callback`. Dev credentials: `akadmin/devpassword`, `developer/devpassword`.

### Testing Patterns

- **Backend:** pytest + pytest-mock + pytest-asyncio (`asyncio_mode = auto` in `setup.cfg`) in `tests/unit/reporting/`. All test functions are `async def`. Use `httpx.AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://test")` for route tests. Override auth via `app.dependency_overrides[get_current_user] = lambda: CurrentUser(...)`. Mock async service calls with `AsyncMock`. See `tests/unit/reporting/routes/query_test.py` for the reference pattern.
- **Frontend:** React Testing Library + Jest (Bun) in `__tests__/` subdirs next to components

### Typing

Strict mypy: `check_untyped_defs = true`, `disallow_untyped_defs = true`.
- All functions must have complete type annotations.
- Fix type errors rather than suppressing with `# type: ignore`.
- When touching existing `# type: ignore` comments, fix the underlying issue and remove them.
- Use `typing.cast` only for known-safe invariants the type system can't express.

## Frontend Style Guide

### List Views

- Top bar: `<Typography variant="h1">` left, `<Button variant="contained">` right.
- Loading: `<CircularProgress />` inline. Error: `<Error />` icon + `<Typography>` in flex row.
- Table: `<TableContainer component={Paper} variant="outlined">` wrapping `<Table>`.
- Empty state: `<TableRow>` with `<TableCell colSpan={N}>` + `<Typography color="text.secondary">` — not a separate card.
- Rows: `<TableRow hover>`. Metadata cells: `sx={{ color: 'text.secondary' }}`. Dates: `new Date(v).toLocaleString()`. Users: `<UserDisplay userId={...} />`.

**Column name conventions:** Latest Update, Updated By, Created By, Version, Status.

**Per-row actions:** `RowMenu` (three-dot `<IconButton size="small"><MoreVertIcon /></IconButton>` in `<Tooltip title="More actions">`). `anchorOrigin/transformOrigin` bottom/top right. `minWidth: 180`. Destructive actions at bottom behind `<Divider />` with `color: 'error.main'`. Disabled items wrapped in `<Tooltip>` + `<span>`.

**Clickable names:** `sx={{ cursor: 'pointer', '&:hover': { textDecoration: 'underline' } }}` on `<Typography>` (not `<Link>`) when click opens a dialog.

**Detail dialogs (read-only):** Shared component in `src/components/`. Title + optional secondary label + close `<IconButton>`. `<Divider />` below title. `Section` sub-component with `color="text.secondary"` label. Code blocks: `<Box component="pre">` with `bgcolor: 'action.hover'`, `fontFamily: 'monospace'`, `whiteSpace: 'pre-wrap'`, `wordBreak: 'break-word'`.

**Create/delete dialogs:** `maxWidth="sm" fullWidth` (create), `maxWidth="xs" fullWidth` (delete with `<DialogContentText>` + `<strong>` name). `<CircularProgress size={20} />` in submit button while in-flight. Errors in `<Alert severity="error">` at top of `<DialogContent>`.

**Version history pages:** Route `<entity>/:id/history`. Back button `<Button startIcon={<ArrowBackIcon />}>`. Title: `<HistoryIcon color="action" />` + `<Typography variant="h1">Version history – {name}</Typography>`. Columns: Version, Saved, Created By, Comment, actions. Current version: bold + `"current"` in `color="primary"`. Restore: disabled on current with tooltip; `comment: \`Restored from version ${version}\``. Helmet: `History – {name} | Seizu`.

## Keeping Supporting Files Up to Date

When changing the codebase, update as needed:
- **`Makefile`** — new build/test/tool targets
- **`.github/workflows/`** — CI for new test/lint steps
- **`Dockerfile` / `docker-compose.yml`** — new services, files, env vars
- **`.pre-commit-config.yaml`** — linting/formatting changes
- **`Pipfile` + `Pipfile.lock`** — always commit together; run `pipenv lock` then `make lock` after edits
- **`docs/`** — update for any user-facing changes; grep for removed items
- **`schema/reporting-schema.json`** — `make schema` after Pydantic schema changes
- **`.env.example`** — add/remove env vars
- **`AGENTS.MD`** — update when conventions or tooling change
