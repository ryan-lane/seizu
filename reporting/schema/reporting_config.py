from typing import Any
from typing import Dict
from typing import List
from typing import Literal
from typing import Optional

from pydantic import BaseModel
from pydantic import Field
from pydantic import field_validator


class InputDefault(BaseModel):
    label: str = Field(
        description="The label for the default.",
    )

    value: str = Field(
        description="The value for the default.",
    )


class Input(BaseModel):
    input_id: str = Field(
        description="Reference to the query in the inputs section.",
        examples=["cve_base_severity"],
    )

    label: str = Field(
        description="The label to use for the select element.",
        examples=["CVE base severity"],
    )

    type: Literal["autocomplete", "text"] = Field(
        description="The type of input to use.",
        examples=["autocomplete"],
    )

    cypher: Optional[str] = Field(
        default=None,
        description="The Cypher query to execute. Must return ``value``.",
        examples=[
            """
            .. code-block:: cypher

              MATCH (c:CVE)
              RETURN DISTINCT c.base_severity AS value
            """
        ],
    )

    default: Optional[InputDefault] = Field(
        default=None,
        description="The default value to set if no value is selected.",
        examples=[
            """
            .. code-block:: yaml

              label: (all)
              value: .*
            """
        ],
    )

    size: Optional[int] = Field(
        default=2,
        description="The size of the input element.",
        examples=["2"],
    )


class BarPanelSettings(BaseModel):
    legend: Optional[str] = Field(
        default=None,
        description=(
            "The type of legend to use; ``row`` or ``column``. If unset,"
            " then no legend will be used."
        ),
    )


class PiePanelSettings(BaseModel):
    legend: Optional[str] = Field(
        default=None,
        description=(
            "The type of legend to use; ``row`` or ``column``. If unset,"
            " then no legend will be used, and arc labels will be used"
            " instead."
        ),
    )


class GraphPanelSettings(BaseModel):
    node_label: Optional[str] = Field(
        default=None,
        description=(
            "The node property to display as the node label."
            " Defaults to ``label`` if unset."
        ),
    )

    node_color_by: Optional[str] = Field(
        default=None,
        description=(
            "The node property to use for color grouping."
            " Defaults to ``group`` if unset."
        ),
    )


class PanelParam(BaseModel):
    name: str = Field(
        description="The parameter name to use when passing this input into the query.",
        examples=["severity"],
    )

    input_id: Optional[str] = Field(
        default=None,
        description="Reference to the query in the inputs section.",
        examples=["cve_base_severity"],
    )

    value: Optional[Any] = Field(
        default=None,
        description="The parameter value to pass into the query.",
        examples=[
            """
            .. code-block:: yaml

              params:
                - name: integrityImpact
                  value: HIGH
            """
        ],
    )


class Panel(BaseModel):
    type: Literal[
        "table",
        "vertical-table",
        "count",
        "bar",
        "pie",
        "graph",
        "progress",
        "markdown",
    ] = Field(
        description="The type of panel to use.",
        examples=["table"],
    )

    cypher: Optional[str] = Field(
        default=None,
        description="A reference to a cypher from the cypher section of the configuration.",
        examples=["cves"],
    )

    details_cypher: Optional[str] = Field(
        default=None,
        description=(
            "A reference to a cypher from the cypher section of the configuration."
            " Used in the details section of the panel, as a table."
            " The query can return rows in any of the formats supported by the"
            " ``table`` panel type."
        ),
        examples=["cves-details"],
    )

    params: List[PanelParam] = Field(
        default_factory=list,
        description=(
            "A list of parameters to send into the query. The parameters can"
            " directly have values, or can be a reference to an input."
        ),
        examples=[
            """
            .. code-block:: yaml

              params:
                - name: severity
                  input_id: cve_base_severity
                - name: integrityImpact
                  value: HIGH
            """
        ],
    )

    caption: Optional[str] = Field(
        default=None,
        description="The caption to use for the panel.",
        examples=["Critical CVEs"],
    )

    table_id: Optional[str] = Field(
        default=None,
        description=(
            "The cypher attribute to use for the table's unique ID, if using a"
            " type of table or vertical-table. If not set, a random ID will be"
            " generated. A table_id should be set for ``vertical-table``, or"
            " the panel will have a random ID used as the caption."
        ),
        examples=["cve_id"],
    )

    markdown: Optional[str] = Field(
        default=None,
        description=(
            "The markdown to use for the panel. Only used for type ``markdown``."
        ),
        examples=[
            """
            .. code-block:: markdown

                ## Affects

                Versions x.x.x - x.x.x

                ## Recommended action

                Upgrade to the latest version of the software.
            """
        ],
    )

    size: Optional[int] = Field(
        default=2,
        description="The size of the panel.",
        examples=["2"],
    )

    threshold: Optional[float] = Field(
        default=None,
        description="The size of the panel.",
        examples=["70"],
    )

    bar_settings: Optional[BarPanelSettings] = Field(
        default=None,
        description="Settings specific to bar panels.",
        examples=[
            """
            .. code-block:: yaml

              bar_settings:
                legend: column
            """
        ],
    )

    pie_settings: Optional[PiePanelSettings] = Field(
        default=None,
        description="Settings specific to pie panels.",
        examples=[
            """
            .. code-block:: yaml

              pie_settings:
                legend: column
            """
        ],
    )

    graph_settings: Optional[GraphPanelSettings] = Field(
        default=None,
        description="Settings specific to graph panels.",
        examples=[
            """
            .. code-block:: yaml

              graph_settings:
                node_label: label
                node_color_by: group
            """
        ],
    )

    metric: Optional[str] = Field(
        default=None,
        description=(
            "The statsd metric to send from the panel data."
            " Only used for ``count`` and ``progress`` panels."
        ),
        examples=["cves.severity"],
    )


class Row(BaseModel):
    name: str = Field(
        description="The name of the row; shown as title above the row.",
        examples=["CVEs"],
    )

    panels: List[Panel] = Field(
        description="The panels to show in the row.",
        examples=[
            """
            .. code-block:: yaml

              panels:
                - cypher: cves-by-severity
                  details_cypher: cves-by-severity-details
                  type: count
                  params:
                    base_severity: CRITICAL
                  caption: Critical CVEs
                  size: 2
            """
        ],
    )


class Report(BaseModel):
    schema_version: int = Field(
        default=1,
        description=(
            "The schema version of the report config."
            " Increment when making breaking changes to the report schema."
        ),
        examples=[1],
    )

    name: str = Field(
        description="The name of the report.",
        examples=["CVEs"],
    )

    queries: Dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Named Cypher queries for this report."
            " Panel ``cypher`` fields may reference a key from this dict,"
            " or provide a Cypher query string directly."
        ),
        examples=[
            """
            .. code-block:: yaml

              queries:
                cves-total: |-
                  MATCH (c:CVE)
                  RETURN count(c.id) AS total
            """
        ],
    )

    inputs: List[Input] = Field(
        default_factory=list,
        description="The inputs to use for the report.",
        examples=[
            """
            .. code-block:: yaml

              inputs:
                - input_id: cve_base_severity
                  cypher: |-
                    MATCH (c:CVE)
                    RETURN c.base_severity AS base_severity
                  default:
                    label: (all)
                    value: .*
                  label: Base Severity
                  type: autocomplete
                  size: 2
            """
        ],
    )

    rows: List[Row] = Field(
        default_factory=list,
        description="The rows of the report.",
        examples=[
            """
            .. code-block:: yaml

              rows:
                - name: "CVEs"
                  panels:
                    - cypher: cves
                      type: table
                      params:
                        - name: severity
                          input_id: cve_base_severity
                      size: 12
            """
        ],
    )


class ScheduledQueryWatchScan(BaseModel):
    grouptype: Optional[str] = Field(
        default=".*",
        description=(
            "Match against the grouptype attribute of the SyncMetadata"
            " node, as a regex. If not set, the query will match against"
            " ``.*``."
        ),
        examples=["CVE"],
    )

    syncedtype: Optional[str] = Field(
        default=".*",
        description=(
            "Match against the syncedtype attribute of the SyncMetadata"
            " node, as a regex. If not set, the query will match against"
            " ``.*``."
        ),
        examples=["year"],
    )

    groupid: Optional[str] = Field(
        default=".*",
        description=(
            "Match against the groupid attribute of the SyncMetadata"
            " node, as a regex. If not set, the query will match against"
            " ``.*``."
        ),
        examples=["2019"],
    )


class ScheduledQueryAction(BaseModel):
    action_type: str = Field(
        description="The type of action to perform.",
        examples=["slack", "sqs"],
    )

    action_config: Dict[str, Any] = Field(
        description=(
            "The configuration for the action. See the documentation for the"
            " relevant scheduled query module for information about the"
            " configuration needed for each action type."
        ),
        examples=[
            """
            .. code-block:: yaml

              action_config:
                webhook_url: https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX
                channel: #cve
                username: CVE
                icon_emoji: :cve:
            """
        ],
    )


class ScheduledQueryParam(BaseModel):
    name: str = Field(
        description="The parameter name to use when passing this input into the query.",
        examples=["severity"],
    )

    value: Any = Field(
        description="The parameter value to pass into the query.",
        examples=[
            """
            .. code-block:: yaml

              params:
                - name: integrityImpact
                  value: HIGH
            """
        ],
    )


class ScheduledQuery(BaseModel):
    name: str = Field(
        description="The name of the scheduled query.",
        examples=["Recently published HIGH/CRITICAL CVEs"],
    )

    cypher: str = Field(
        description="The cypher to use for the scheduled query.",
        examples=["recent-cves"],
    )

    params: List[ScheduledQueryParam] = Field(
        default_factory=list,
        description=(
            "A dictionary of parameters to pass to the cypher query. The keys"
            " are the variable names, and the values are the values to pass."
        ),
        examples=[
            """
            .. code-block:: yaml

              params:
                - name: syncedtype
                  value:
                    - recent
                - name: base_severity
                  value:
                    - HIGH
                    - CRITICAL
            """
        ],
    )

    frequency: Optional[int] = Field(
        default=None,
        description=(
            "The frequency of the scheduled query in minutes. Mutually"
            " exclusive with ``watch_scans``."
        ),
        examples=["1440"],
    )

    watch_scans: List[ScheduledQueryWatchScan] = Field(
        default_factory=list,
        description=(
            "The scans to watch for the scheduled query. Based on"
            " SyncMetadata. Query will triger if any of the watched"
            " scans listed are updated. Mutually exclusive with"
            " ``frequency``."
        ),
        examples=[
            """
            .. code-block:: yaml

              watch_scans:
                - grouptype: CVE
                  syncedtype: recent
                - grouptype: CVE
                  syncedtype: modified
            """
        ],
    )

    enabled: Optional[bool] = Field(
        default=True,
        description=(
            "Whether the scheduled query should be enabled. If not set, the"
            " scheduled query will be enabled."
        ),
        examples=["true"],
    )

    actions: List[ScheduledQueryAction] = Field(
        default_factory=list,
        description=("The actions to perform when the scheduled query is triggered."),
        examples=[
            """
            .. code-block:: yaml

              actions:
                - action_type: slack
                  title: Recently published HIGH/CRITICAL CVEs
                  initial_comment: |
                    The following HIGH/CRITICAL CVEs have been published in the last 24 hours.
                  channels:
                    - C0000000000
            """
        ],
    )


class ReportingConfig(BaseModel):
    queries: Dict[str, str] = Field(
        default_factory=dict,
        description="The queries to use for the report.",
        examples=[
            """
            .. code-block:: yaml

              queries:
                cves-severity-of-total: |-
                  MATCH (c:CVE)
                  WITH COUNT(DISTINCT c.id) AS denominator
                  MATCH (c:CVE)
                  WHERE c.base_severity = "CRITICAL"
                  RETURN count(DISTINCT c.id) AS numerator, denominator
                cves-by-severity: |-
                  MATCH (c:CVE)
                  WHERE c.base_severity = $base_severity
                  RETURN count(c.id) AS count
                cves: |-
                  MATCH (c:CVE)
                  WHERE c.base_severity =~ ($base_severity)
                  RETURN {
                    cve_id: c.id,
                    base_severity: c.base_severity,
                    severity: c.severity,
                    description: c.description
                  } AS details
                  ORDER BY details.severity DESC
                recent-cves: |-
                  MATCH (s:SyncMetadata)
                  WHERE s.grouptype = "CVE" AND s.syncedtype IN $syncedtype
                  WITH datetime({epochSeconds: s.lastupdated}) - duration({hours: 24}) AS feedupdatetime
                  MATCH (c:CVE)
                  WHERE (datetime(c.published_date) > feedupdatetime AND c.base_severity IN $base_severity
                  RETURN {
                    id: c.id,
                    base_severity: c.base_severity,
                    base_score: c.base_score,
                    description: c.description_en
                  } AS details
            """
        ],
    )

    dashboard: Optional[str] = Field(
        default=None,
        description=(
            "Key of the report in the ``reports`` section to use as the default"
            " dashboard. If unset, no report is displayed on the dashboard page."
        ),
        examples=["dashboard"],
    )

    reports: Dict[str, Report] = Field(
        default_factory=dict,
        description="The reports to use for the report.",
        examples=[
            """
            .. code-block:: yaml

              reports:
                cves:
                  name: CVEs
                  inputs:
                    - input_id: cve_base_severity
                      cypher: |-
                        MATCH (c:CVE)
                        RETURN c.base_severity AS base_severity
                      default:
                        label: (all)
                        value: .*
                      label: Base Severity
                      type: autocomplete
                      size: 2
                  rows:
                    - name: CVEs
                      panels:
                        - cypher: cves
                          type: table
                          params:
                            - name: severity
                              input_id: cve_base_severity
                          size: 12
            """
        ],
    )

    scheduled_queries: List[ScheduledQuery] = Field(
        default_factory=list,
        description="The scheduled queries to run.",
        examples=[
            """
            .. code-block:: yaml

              scheduled_queries:
                - name: CVEs by severity
                  cypher: recent-cves
                  frequency: 1440
                  watch_scans:
                    - grouptype: CVE
                      syncedtype: recent
                  actions:
                    - action_type: slack
                      action_config:
                        title: Recently published HIGH/CRITICAL CVEs
            """
        ],
    )

    @field_validator("scheduled_queries", mode="before")
    @classmethod
    def coerce_scheduled_queries(cls, v: Any) -> Any:
        """Accept old dict format (key -> ScheduledQuery) as well as the new list format."""
        if isinstance(v, dict):
            return list(v.values())
        return v


def output_json_schema() -> Dict[str, Any]:
    schema = ReportingConfig.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    return schema
