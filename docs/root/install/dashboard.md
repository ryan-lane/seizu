# Dashboard Configuration

## Navigation Sections

Seizu's navigation supports a dashboard and an arbitrary number of reports.
The dashboard is the landing page, and is meant as a general overview of the data in your graph.
Reports are topic-specific views of your graph data.

Both the dashboard and reports use a list of rows, which contain a list of panels; both are grid-based.
Rows are rendered in the order specified, and panels within rows are also rendered in the order specified.

## Configuration Storage

Report and dashboard configurations are stored in DynamoDB, not in the YAML configuration file.
The YAML file contains a top-level `queries` dict (used only by `scheduled_queries` references), `scheduled_queries`, a `dashboard` pointer, and a `reports` section used to seed DynamoDB.
Each report has its own `queries` dict for named Cypher strings used by its panels.

To populate DynamoDB from the YAML file during initial setup or development:

```bash
make seed_reports
```

The `dashboard` key in the YAML file is a string that names a report in the `reports` section to use as the default dashboard:

```yaml
dashboard: dashboard   # pointer to the "dashboard" entry in reports

reports:
  dashboard:
    name: Dashboard
    queries:
      cves-total: |-
        MATCH (c:CVE)
        RETURN count(c.id) AS total
    rows:
      - name: Overview
        panels:
          - cypher: cves-total       # reference to a named query in this report's queries dict
            type: count
            caption: Total CVEs
            size: 3
          - cypher: |-               # direct Cypher string — no named reference needed
              MATCH (c:CVE)
              RETURN count(c.id) AS total
            type: count
            caption: Total CVEs (direct)
            size: 3
```

To change the dashboard at runtime, use the Reports list in the UI (see below) or call the API directly:

```bash
curl -X PUT /api/v1/reports/<report_id>/dashboard
```

## Managing Reports

Reports can be created, edited, and deleted at runtime through the Seizu UI without modifying the YAML file or restarting the service.

### Reports list

Navigate to **Reports** in the sidebar to view all reports. From the list you can:

- Click a report name to view it.
- Open the **⋮** menu on any row to **Edit**, **Set as dashboard**, or **Delete** a report.
- A **Dashboard** badge is shown inline on whichever report is currently set as the dashboard.

### Creating a report

Click **New report** on the Reports list page, enter a name, and confirm. An empty report is created immediately and opened in edit mode so you can start adding rows and panels.

### Editing a report

Click **Edit report** (top-right when viewing a report) or choose **Edit** from the ⋮ menu in the Reports list. Edit mode provides:

- **Named Queries** — a collapsible section for defining reusable Cypher strings that panels can reference by key.
- **Rows** — add, rename, and delete rows. Rows hold panels in a horizontal grid.
- **Panels** — within each row, panels can be dragged to a new position (within a row or to a different row) and resized using the − / + column controls (1–12 grid columns). Use the pencil icon to open the panel editor, or the trash icon to remove a panel.
- **Add panel** — opens the panel editor where you select the panel type and fill in the relevant fields. The form adapts to show only the fields applicable to the chosen type.

Click **Save version** to commit your changes. Every save creates a new numbered version; existing versions are never overwritten.

### Deleting a report

Choose **Delete** from the ⋮ menu in the Reports list and confirm. This permanently removes the report and all its versions. If the report was set as the dashboard, the dashboard pointer is also cleared.

## Panels

Seizu supports various panel types that can be used to visualize graph data.
See [the Panel schema](schema.html#panel) for more detailed info about specific fields.

### count

To simply display a count of a particular query, use a ``count`` panel.

![a count panel example](/images/count-panel.png)

| Field | Description |
|-------|-------------|
| cypher | A cypher query to use for this panel. Either a key from the report's `queries` dict, or a direct Cypher string. The query must return the count as ``total``. |
| details\_cypher | A cypher to use for displaying a table view of the data, in a details view. Either a key from the report's `queries` dict, or a direct Cypher string. The query must return the rows as ``details``. |
| params | A list of parameters to pass into the query. See [the PanelParam schema](schema.html#panelparam) for more info. |
| caption | The caption to show as the title of this panel. |
| type | The type of panel. ``count``, for this panel type. |
| metric | The statsd metric to push for this panel, if stats pushing is enabled. |
| size | The width of this panel. |

#### Example

```yaml
        - cypher: cves
          details_cypher: cves-details
          caption: Total CVEs
          metric: cves.total
          type: count
          size: 3
```

### progress

To display a progress wheel, and x/y display of a particular query, use a ``progress`` panel.
By default, this panel will color the progress data based on a threshold of <70% error, >70% <100% primary, 100% success.

![a progress panel example](/images/progress-panel.png)

| Field | Description |
|-------|-------------|
| cypher | A cypher query to use for this panel. Either a key from the report's `queries` dict, or a direct Cypher string. The query must return the counts as ``numerator`` and ``denominator``. |
| details\_cypher | A cypher to use for displaying a table view of the data, in a details view. Either a key from the report's `queries` dict, or a direct Cypher string. The query must return the rows as ``details``. |
| params | A list of parameters to pass into the query. See [the PanelParam schema](schema.html#panelparam) for more info. |
| caption | The caption to show as the title of this panel. |
| type | The type of panel. ``progress``, for this panel type. |
| threshold | The lower threshold percentage to consider this result an error. Set to `0` to disable threshold. Default: ``70`` |
| metric | The statsd metric to push for this panel, if stats pushing is enabled. |
| size | The width of this panel. |

#### Example

```yaml
        - cypher: cve-by-severity
          details_cypher: cve-by-severity-details
          params:
            - name: severity
              value: CRITICAL
          caption: Critical CVEs
          type: progress
          threshold: 0
          size: 3
```

### pie

To display a pie graph, use a ``pie`` panel.

![a pie panel example with a column legend](/images/pie-panel-legend-column.png)

| Field | Description |
|-------|-------------|
| cypher | A cypher query to use for this panel. Either a key from the report's `queries` dict, or a direct Cypher string. The query must return rows, formatted as a dictionary, with keys ``id`` and ``value``, as a detail; example: ``RETURN {id: c.base_severity, value: count(c.id)} AS details``
| details\_cypher | A cypher to use for displaying a table view of the data, in a details view. Either a key from the report's `queries` dict, or a direct Cypher string. The query must return the rows as ``details``. |
| params | A list of parameters to pass into the query. See [the PanelParam schema](schema.html#panelparam) for more info. |
| caption | The caption to show as the title of this panel. |
| type | The type of panel. ``pie``, for this panel type. |
| pie\_settings | An object of settings specific to pie panels. |
| pie\_settings.legend | Orientation of the legend. ``row`` or ``column``. If legend is not set, no legend will be shown, and arc labels will be shown instead. |
| size | The width of this panel. |

#### Example

```yaml
        - cypher: cves-by-severity-as-rows
          caption: Critical CVEs
          type: pie
          pie_settings:
            legend: column
          size: 3
```

### bar

To display a bar graph, use a ``bar`` panel.

![a bar panel example](/images/bar-panel.png)

| Field | Description |
|-------|-------------|
| cypher | A cypher query to use for this panel. Either a key from the report's `queries` dict, or a direct Cypher string. The query must return rows, formatted as a dictionary, with keys ``id`` and ``value``, as a detail; example: ``RETURN {id: c.base_severity, value: count(c.id)} AS details``
| details\_cypher | A cypher to use for displaying a table view of the data, in a details view. Either a key from the report's `queries` dict, or a direct Cypher string. The query must return the rows as ``details``. |
| params | A list of parameters to pass into the query. See [the PanelParam schema](schema.html#panelparam) for more info. |
| caption | The caption to show as the title of this panel. |
| type | The type of panel. ``bar``, for this panel type. |
| bar\_settings | An object of settings specific to bar panels. |
| bar\_settings.legend | Orientation of the legend. ``row`` or ``column``. |
| size | The width of this panel. |

#### Example

```yaml
        - cypher: cves-by-severity-as-rows
          caption: Critical CVEs
          type: bar
          bar_settings:
            legend: column
          size: 3
```

### table

To display rows in a paged table, use a ``table`` panel.

![a table panel example](/images/table-panel.png)

| Field | Description |
|-------|-------------|
| cypher | A cypher query to use for this panel. Either a key from the report's `queries` dict, or a direct Cypher string. The query must return the rows as ``details``. |
| params | A list of parameters to pass into the query. See [the PanelParam schema](schema.html#panelparam) for more info. |
| caption | The caption to show as the title of this panel. |
| type | The type of panel. ``table``, for this panel type. |
| size | The width of this panel. |

#### Example

```yaml
      - name: CVEs
        panels:
          - cypher: cve-search
            params:
              - name: cveId
                input_id: cve-id-autocomplete-input
            type: table
            size: 12
```

### vertical-table

To display rows in a less-dense, vertical per-row view, use a ``vertical-table`` panel.
Note: the caption per-row is set via the ``table_id`` field, and if unset, will display ``undefined``

![a vertical table panel example](/images/vertical-table-panel.png)

| Field | Description |
|-------|-------------|
| cypher | A cypher query to use for this panel. Either a key from the report's `queries` dict, or a direct Cypher string. The query must return the rows as ``details``. |
| params | A list of parameters to pass into the query. See [the PanelParam schema](schema.html#panelparam) for more info. |
| caption | The caption to show as the title of this panel. |
| type | The type of panel. ``vertical-table``, for this panel type. |
| table\_id | The attribute inside of the ``details`` dictionary to use as a caption for each row. If not set, row captions will show as ``undefined``. |
| size | The width of this panel. |

#### Example

```yaml
      - name: CVEs
        panels:
          - cypher: cve-search
            params:
              - name: cveId
                input_id: cve-id-autocomplete-input
            type: vertical-table
            table_id: id
            size: 12
```


### markdown

To render markdown, use a ``markdown`` panel.

![a markdown panel example](/images/markdown-panel.png)

| Field | Description |
|-------|-------------|
| markdown | The markdown to render. |
| type | The type of panel. ``markdown``, for this panel type. |
| size | The width of this panel. |

#### Example

```yaml
          - markdown: |-
              ## CVE info
              1. [CVE-2021-44228](https://security.snyk.io/vuln/SNYK-JAVA-ORGAPACHELOGGINGLOG4J-2314720): Remote Code Execution (RCE), affects log4j versions below 2.15.0
              1. [CVE-2021-4104](https://security.snyk.io/vuln/SNYK-JAVA-LOG4J-2316893): Arbitrary Code Execution, affects log4j 1.x
              1. [CVE-2021-45046](https://security.snyk.io/vuln/SNYK-JAVA-ORGAPACHELOGGINGLOG4J-2320014): Remote Code Execution (RCE), affects log4j versions below 2.16.0
              1. [CVE-2021-45105](https://security.snyk.io/vuln/SNYK-JAVA-ORGAPACHELOGGINGLOG4J-2321524): Denial of Service (DoS), affects log4j versions below 2.17.0
              1. [CVE-2021-44832](https://security.snyk.io/vuln/SNYK-JAVA-ORGAPACHELOGGINGLOG4J-2327339): Arbitrary Code Execution (RCE), affects log4j versions below 2.17.1

              ## Recommended action
              Upgrade to log4j 2.17.1 or higher.
            type: markdown
            size: 12
```

## Named Queries

Reports can define a `queries` dict of named Cypher strings.
Panel `cypher` and `details_cypher` fields are resolved against this dict at render time.
If the field value is not a key in the dict, it is used as a literal Cypher string — allowing panels to embed queries directly without adding them to the `queries` dict first.

```yaml
reports:
  dashboard:
    name: Dashboard
    queries:
      cves-total: |-
        MATCH (c:CVE)
        RETURN count(c.id) AS total
    rows:
      - name: Overview
        panels:
          # Named reference — resolved from the queries dict above
          - cypher: cves-total
            type: count
            caption: Total CVEs
            size: 3
          # Direct Cypher string — no entry in queries needed
          - cypher: |-
              MATCH (c:CVE)
              RETURN count(c.id) AS total
            type: count
            caption: Total CVEs (direct)
            size: 3
```

## Inputs

Reports can define inputs that can be used to pass parameters into queries used in panels in the report.
These will be rendered at the top of the report, in the order specified in the configuration.

### autocomplete

An ``autocomplete`` input can be used to use results queried from the graph as inputs to panels.
End-users can select through a dropdown list of the values, or can type to search/autocomplete a value.

![an autocomplete input example](/images/autocomplete-input.png)

| Field | Description |
|-------|-------------|
| input\_id | An ID for this input, that can be referenced from the params section of a panel. |
| cypher | A cypher query used to return the relevant data. This is __not__ a reference to a query, but the actual query to run. It's recommended to use ``DISTINCT`` for the values returned. The query must return the data as ``value``. |
| default | A dictionary with the default ``label`` and ``value`` for the input, when not set. |
| type | The type of input. ``autocomplete``, for this input type. |
| size | The width of this input. |

#### Example

```yaml
      - input_id: cve-severity-autocomplete-input
        cypher: >-
          MATCH (c:CVE)
          RETURN DISTINCT c.base_severity AS value
        label: CVE Severity
        type: autocomplete
        size: 2
```

### text

A ``text`` input can be used for user-defined input for panel query parameters.

![an text input example](/images/text-input.png)

| Field | Description |
|-------|-------------|
| input\_id | An ID for this input, that can be referenced from the params section of a panel. |
| default | A dictionary with the default ``value`` for the input, when not set. |
| type | The type of input. ``text``, for this input type. |
| size | The width of this input. |

#### Example

```yaml
      - input_id: cve-id-regex
        label: Regex
        type: text
        size: 2
```

## Example Configuration

All panel types have an info button, which will show extra details about the panel, such as the query used, the parameters to the query, metrics that may be pushed with it, etc.
Non-table panel types can also show a query related to the panel as more details, in the details view.

![a details view example](/images/details-view.png)

Example configuration

.. literalinclude:: ../../../.config/dev/seizu/reporting-dashboard.yaml
   :language: yaml
