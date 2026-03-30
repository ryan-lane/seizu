# Scheduled Queries

## Purpose

Dashboards are a good visual representation of a system, for when you want to actively check something, but sometimes you want to be passively notified about changes in the graph data.

Seizu can run queries on a set schedule, or when the SyncMetadata graph data changes.
It can take the query results and pass them into a list of configurable actions.

## Managing Scheduled Queries

Scheduled queries are stored in the database and managed through the Seizu UI or API. They are not read directly from the YAML configuration file at runtime.

> **Permissions:** Creating and editing scheduled queries requires the `scheduled_queries:write` permission (`seizu-admin`). Deleting requires `scheduled_queries:delete`. Users with `seizu-viewer` or `seizu-editor` roles can view scheduled queries and history but will not see the **New scheduled query** button, and write/delete actions in the **⋮** menu will be disabled.

### Scheduled Queries list

Navigate to **Scheduled Queries** in the sidebar to view all scheduled queries. From the list you can:

- Click a query name to view its current configuration in a read-only detail dialog.
- Open the **⋮** menu on any row to **Edit**, **View history**, or **Delete** a query.
- The table shows the trigger type, configured actions, enabled status, current version, latest update timestamp, and who last updated each query.

### Creating a scheduled query

Click **New scheduled query** on the Scheduled Queries page. The form includes:

| Field | Description |
|-------|-------------|
| name | A user-friendly name for the scheduled query. |
| cypher | A Cypher query to run. The query must return the data as `details` (or as configured via `query_return_attribute` in the action config). |
| enabled | Whether the query will be run by the worker. |
| trigger | Choose **Fixed frequency** (run every N minutes) or **Watch scans** (run when matching SyncMetadata nodes are updated). |
| frequency | Minutes between runs. Used when trigger is **Fixed frequency**. |
| watch scans | List of SyncMetadata filters. Each entry takes `grouptype`, `syncedtype`, and `groupid` (all support `.*` as a wildcard). Used when trigger is **Watch scans**. |
| params | Query parameters. Each param has a name and a value. Toggle the **list** button to switch between a single value and a comma-separated list of values. |
| actions | One or more actions to run with the query results. See the Built-in Actions section below. |

### Editing a scheduled query

Choose **Edit** from the **⋮** menu. The form is the same as creation. An optional **Comment** field is shown when editing, allowing you to describe what changed.

Every save creates a new numbered version; existing versions are never overwritten.

### Version history

Every save creates a new numbered version. To view the history:

- Choose **View history** from the **⋮** menu in the Scheduled Queries list.

The history page lists all versions newest-first, showing the version number, save date, who created that version, and the save comment. The current (latest) version is labeled **current**.

Click a version number to view the full configuration at that point in time. From the overflow menu on any version row you can **Restore** to save that historical configuration as a new latest version.

Restoring a version never deletes history — it creates a new version whose config matches the restored one, with a comment of `Restored from version N`.

### Deleting a scheduled query

Choose **Delete** from the **⋮** menu and confirm. This permanently removes the query and all its versions.

## YAML Configuration (for seeding)

The YAML configuration file is used only as a seed source — it is not read at runtime by the scheduled query worker.
Scheduled queries can be seeded from the YAML file using:

```bash
make seed_dashboard
```

The `scheduled_queries` section in the YAML uses a **list** format:

```yaml
scheduled_queries:
  - name: Recently published HIGH/CRITICAL CVEs
    cypher: recent-cves          # reference to a key in the top-level queries dict
    params:
      - name: base_severity
        value:
          - HIGH
          - CRITICAL
    frequency: 1440              # every 24 hours
    enabled: true
    actions:
      - action_type: slack
        action_config:
          title: Recently published HIGH/CRITICAL CVEs
          initial_comment: |
            The following HIGH/CRITICAL CVEs have been published in the last 2 hours.
          channels:
            - C00000000

  - name: K8s container images with no vulnerability scans
    cypher: k8s-images-without-scans
    watch_scans:
      - grouptype: KubernetesCluster
        syncedtype: KubernetesCluster
    enabled: true
    actions:
      - action_type: sqs
        action_config:
          sqs_queue: k8s-image-scanner
```

The `cypher` field is resolved against the top-level `queries` dict; if no matching key is found, the value is used as a literal Cypher string.

Seeding is idempotent by name: existing queries are skipped unless their content has changed or `--force` is passed.

## Scheduling

### Fixed frequency

Use the `frequency` field (minutes) to run a query on a regular schedule:

```yaml
  - name: Recently published HIGH/CRITICAL CVEs
    frequency: 1440   # every 24 hours
```

### Watch scans

Use `watch_scans` to trigger a query when Cartography SyncMetadata nodes are updated:

```yaml
  - name: K8s container images with no vulnerability scans
    watch_scans:
      - grouptype: KubernetesCluster
        syncedtype: KubernetesCluster
```

`watch_scans` works by tracking when the query last ran and comparing that time to the SyncMetadata node timestamps. A newly created query will run immediately, then only again after a matching sync is detected.

`frequency` and `watch_scans` are mutually exclusive.

## Built-in Actions

Action configuration forms in the UI are generated dynamically from the schema declared by each module. Required fields are marked with `*`.

### slack

The `slack` action takes query results and attaches them as a CSV to a Slack message.

| Field | Required | Description |
|-------|----------|-------------|
| title | Yes | The title of the Slack message. |
| initial\_comment | Yes | The message body. The CSV is attached to this message. |
| channels | Yes | A list of channel IDs (not names) to send the message to. |
| query\_return\_attribute | No | The attribute in each result row to include. Default: `details` |

Requires the following environment variable:

- `SLACK_OAUTH_BOT_TOKEN`: Slack OAuth bot token for authentication.

### sqs

The `sqs` action enqueues each query result row into an SQS queue.

| Field | Required | Description |
|-------|----------|-------------|
| sqs\_queue | Yes | The SQS queue name to enqueue results into. |
| query\_return\_attribute | No | The attribute in each result row to enqueue. Default: `details` |

Local development options:

- `SQS_CREATE_SCHEDULED_QUERY_QUEUES`: Automatically create the configured queues if they don't exist.
- `SQS_URL`: URL for a local/fake SQS server.

### log

The `log` action logs query results using Python's standard logger. Intended for development and testing; not enabled by default.

| Field | Required | Description |
|-------|----------|-------------|
| log\_attrs | Yes | A list of attributes from each result row to include in the log message. |
| query\_return\_attribute | No | The attribute in each result row to read. Default: `details` |
| message | No | The log message prefix. Default: `Result for <scheduled_query_id>` |
| level | No | Log level: `debug`, `info`, `warning`, `error`. Default: `info` |

To enable the `log` module, add it to `SCHEDULED_QUERY_MODULES`:

```
SCHEDULED_QUERY_MODULES=reporting.scheduled_query_modules.sqs,reporting.scheduled_query_modules.slack,reporting.scheduled_query_modules.log
```

## Custom Actions

Custom actions can be included through Python modules, configured via the `SCHEDULED_QUERY_MODULES` setting (comma-separated module paths; default includes `sqs` and `slack`).

The module must implement the `ModuleInterface`:

.. literalinclude:: ../../../reporting/scheduled_query_modules/__init__.py
    :pyobject: ModuleInterface

Key methods:

- `action_name()` — returns the string identifier used in `action_type`
- `setup()` — called once at worker startup for initialisation (e.g. creating SQS queues)
- `handle_results()` — called with each set of query results
- `action_config_schema()` — **optional but recommended**; returns a list of `ActionConfigFieldDef` objects describing the action's config fields. The UI uses this to generate typed input forms instead of a raw JSON textarea. Required and optional fields, types (`string`, `text`, `number`, `boolean`, `string_list`, `select`), defaults, and help text are all declared here.

Example minimal module:

```python
def action_name() -> str:
    return "print"

def setup() -> None:
    return

def handle_results(
    scheduled_query_id: str,
    action: ScheduledQueryAction,
    results: List[Dict[str, Any]],
) -> None:
    for result in results:
        print(result)

def action_config_schema():
    return []
```

Settings for modules should be fetched within the module itself:

```python
from reporting.utils.settings import str_env

_SLACK_OAUTH_BOT_TOKEN = str_env("SLACK_OAUTH_BOT_TOKEN")
```

## Run the Scheduled Queries Worker

The worker can be run directly:

```bash
python -m reporting.scheduled_queries
```

Or via Docker Compose (the `seizu-scheduled-queries` service).

The worker runs continuously until terminated.
