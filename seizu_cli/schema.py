"""YAML config schema for seizu reporting dashboards.

Mirrors ``reporting/schema/reporting_config.py`` so that the CLI can parse and
serialise the dashboard YAML file without depending on the ``reporting`` package.
"""
from typing import Any
from typing import Dict
from typing import List
from typing import Literal
from typing import Optional

import yaml
from pydantic import BaseModel
from pydantic import Field
from pydantic import field_validator


class InputDefault(BaseModel):
    label: str
    value: str


class Input(BaseModel):
    input_id: str
    label: str
    type: Literal["autocomplete", "text"]
    cypher: Optional[str] = None
    default: Optional[InputDefault] = None
    size: Optional[int] = 2


class BarPanelSettings(BaseModel):
    legend: Optional[str] = None


class PiePanelSettings(BaseModel):
    legend: Optional[str] = None


class GraphPanelSettings(BaseModel):
    node_label: Optional[str] = None
    node_color_by: Optional[str] = None


class PanelParam(BaseModel):
    name: str
    input_id: Optional[str] = None
    value: Optional[Any] = None


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
    ]
    cypher: Optional[str] = None
    details_cypher: Optional[str] = None
    params: List[PanelParam] = Field(default_factory=list)
    caption: Optional[str] = None
    table_id: Optional[str] = None
    markdown: Optional[str] = None
    size: Optional[int] = 2
    threshold: Optional[float] = None
    bar_settings: Optional[BarPanelSettings] = None
    pie_settings: Optional[PiePanelSettings] = None
    graph_settings: Optional[GraphPanelSettings] = None
    metric: Optional[str] = None


class Row(BaseModel):
    name: str
    panels: List[Panel]


class Report(BaseModel):
    schema_version: int = 1
    name: str
    queries: Dict[str, str] = Field(default_factory=dict)
    inputs: List[Input] = Field(default_factory=list)
    rows: List[Row] = Field(default_factory=list)


class ScheduledQueryWatchScan(BaseModel):
    grouptype: Optional[str] = ".*"
    syncedtype: Optional[str] = ".*"
    groupid: Optional[str] = ".*"


class ScheduledQueryAction(BaseModel):
    action_type: str
    action_config: Dict[str, Any]


class ScheduledQueryParam(BaseModel):
    name: str
    value: Any


class ScheduledQuery(BaseModel):
    name: str
    cypher: str
    params: List[ScheduledQueryParam] = Field(default_factory=list)
    frequency: Optional[int] = None
    watch_scans: List[ScheduledQueryWatchScan] = Field(default_factory=list)
    enabled: Optional[bool] = True
    actions: List[ScheduledQueryAction] = Field(default_factory=list)


class ReportingConfig(BaseModel):
    queries: Dict[str, str] = Field(default_factory=dict)
    dashboard: Optional[str] = None
    reports: Dict[str, Report] = Field(default_factory=dict)
    scheduled_queries: List[ScheduledQuery] = Field(default_factory=list)

    @field_validator("scheduled_queries", mode="before")
    @classmethod
    def coerce_scheduled_queries(cls, v: Any) -> Any:
        """Accept old dict format (key -> ScheduledQuery) as well as the new list format."""
        if isinstance(v, dict):
            return list(v.values())
        return v


def dump_yaml(config: ReportingConfig) -> str:
    return yaml.dump(
        config.model_dump(),
        default_flow_style=False,
        allow_unicode=True,
    )


def load_file(path: str) -> ReportingConfig:
    with open(path) as f:
        return ReportingConfig.model_validate(yaml.safe_load(f))
