from typing import Any

from pydantic import BaseModel


class QueryRequest(BaseModel):
    query: str
    params: dict[str, Any] | None = None


class ReportQueryRequest(BaseModel):
    token: str
    params: dict[str, Any] | None = None


class QueryResponse(BaseModel):
    results: list[dict[str, Any]]
    errors: list[str] = []
    warnings: list[str] = []
    history_id: str | None = None


class HistoryQueryRequest(BaseModel):
    history_id: str


class ValidationResponse(BaseModel):
    errors: list[str]
    warnings: list[str]


class GraphSchemaResponse(BaseModel):
    labels: list[str]
    relationship_types: list[str]
    property_keys: list[str]
