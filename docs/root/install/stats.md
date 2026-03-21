# Pushing Panel Data to Statsd

## Purpose

Systems like cartography and starbase are "point in time".
This approach makes it easy to query the current state of the data, but sometimes having a view of the data over a period of time is needed to see trends.
Seizu can, under some conditions, push query data into metrics systems, using statsd.

## How to push metrics

### Configure statsd in the backend

See the [backend configuration for statsd](backend.html#statsd-configuration)

### Set ``metric`` on panels

Panel configurations, including the ``metric`` field, are stored in the report store (DynamoDB or SQLModel).
Configure panels through the Seizu UI or by seeding from the YAML file with ``make seed_reports``.
When a report version is saved, the stats worker's index is updated automatically — no separate step is needed.

The ``metric`` setting on a panel is the prefix of the metric.
The full name of the metrics being pushed depend on the panel type.
For example, the following panel configuration would take the the ``total`` value from the ``count`` panel and push it to the ``cves.count.total`` metric.

```yaml
        - cypher: cves
          details_cypher: cves-details
          caption: Total CVEs
          metric: cves.count
          type: count
          size: 2.4
```

The following panel configuration would take the ``numerator`` and ``denominator`` values from the ``progress`` panel and push it to the ``cves.severity.numerator`` and ``cves.severity.denominator`` metric.

```yaml
        - cypher: cve-by-severity
          details_cypher: cve-by-severity-details
          caption: Critical CVEs
          metric: cves.severity
          type: progress
          threshold: 0
          size: 2.4
```

When parameters are used, the parameters would be pushed along with the metric as metric tags.
For example, the following panel configuration would take the ``numerator`` and ``denominator`` values from the ``progress`` panel and push it to the ``cves.severity.numerator`` and ``cves.severity.denominator`` metric, with a metric tag of ``severity: CRITICAL``:

```yaml
        - cypher: cve-by-severity
          details_cypher: cve-by-severity-details
          params:
            - name: severity
              value: CRITICAL
          caption: Critical CVEs
          type: progress
          threshold: 0
          size: 2.4
```

If the parameter is an input, rather than an explicit value, the query will be run against every input value, and a metric will be pushed for every value, adding the input value as a metric tag.
This can lead to stats with very high cardinality; see the limitation sections about this.

### Run the ``dashboard-stats`` worker, in a cron

The worker can be run as a flask CLI command:

```bash
$> export FLASK_APP=reporting.dashboard_stats
$> flask worker dashboard-stats
```

The worker reads pre-computed stat descriptors directly from the configured report store (DynamoDB or SQLModel), so it needs access to the same store backend as the main seizu service.
It does **not** read the YAML configuration file.

This worker runs and exits, so to push stats on a schedule, the worker should be run as a cron on the preferred schedule.

## Limitations

* ``metric`` configuration is only support by specific panel types; currently: ``count``, ``progress``
* Panels with inputs can push metrics, but only for panels with a single input, and only if the input has less values than the configuration variable `DASHBOARD_STATS_MAX_INPUT_RESULTS` allows. This is to avoid sending stats with too much cardinality.
* The stats forwarder (or metrics backend) you have configured must support tags.
