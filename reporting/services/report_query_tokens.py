"""Signed report-query capability helpers."""

from __future__ import annotations

import base64
import hmac
import json
import time
from hashlib import sha256
from typing import Any

from reporting import settings
from reporting.authnz import CurrentUser
from reporting.schema.report_config import ReportVersion

_CAPABILITY_KIND = "report_query"
_CAPABILITY_VERSION = 1
_DEV_FALLBACK_SECRET = "seizu-dev-report-query-signing-secret"
_DEV_FALLBACK_TTL_SECONDS = 15 * 60


class QueryTokenExpiredError(ValueError):
    """Raised when a report query token's expiry timestamp has passed."""


def _get_signing_secret() -> bytes:
    secret = settings.REPORT_QUERY_SIGNING_SECRET
    if secret:
        return secret.encode("utf-8")
    if not settings.DEVELOPMENT_ONLY_REQUIRE_AUTH:
        return _DEV_FALLBACK_SECRET.encode("utf-8")
    raise RuntimeError("REPORT_QUERY_SIGNING_SECRET must be configured")


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _json_default(value: Any) -> Any:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _dump_payload(payload: dict[str, Any]) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=_json_default,
    ).encode("utf-8")


def _sign_payload(payload: dict[str, Any]) -> str:
    payload_bytes = _dump_payload(payload)
    encoded_payload = _b64url_encode(payload_bytes)
    signature = hmac.new(_get_signing_secret(), encoded_payload.encode("ascii"), sha256).digest()
    return f"{encoded_payload}.{_b64url_encode(signature)}"


def _verify_signed_token(token: str) -> dict[str, Any]:
    try:
        encoded_payload, encoded_sig = token.split(".", 1)
    except ValueError as exc:
        raise ValueError("Invalid report query token") from exc

    expected_sig = hmac.new(_get_signing_secret(), encoded_payload.encode("ascii"), sha256).digest()
    try:
        actual_sig = _b64url_decode(encoded_sig)
    except Exception as exc:  # pragma: no cover - defensive
        raise ValueError("Invalid report query token signature") from exc
    if not hmac.compare_digest(expected_sig, actual_sig):
        raise ValueError("Invalid report query token signature")

    try:
        payload = json.loads(_b64url_decode(encoded_payload))
    except Exception as exc:  # pragma: no cover - defensive
        raise ValueError("Invalid report query token payload") from exc

    if not isinstance(payload, dict):
        raise ValueError("Invalid report query token payload")
    return payload


def _get_token_expiry(current_user: CurrentUser) -> int:
    token_exp = current_user.jwt_claims.get("token_exp")
    if token_exp is None:
        if not settings.DEVELOPMENT_ONLY_REQUIRE_AUTH:
            return int(time.time()) + _DEV_FALLBACK_TTL_SECONDS
        raise RuntimeError("JWT exp claim is required to sign report query tokens")
    return int(token_exp.timestamp())


def _build_token_payload(
    *,
    current_user: CurrentUser,
    report_id: str,
    report_version: int,
    path: str,
    query: str,
    allowed_param_names: list[str],
    static_params: dict[str, Any],
) -> dict[str, Any]:
    return {
        "v": _CAPABILITY_VERSION,
        "kind": _CAPABILITY_KIND,
        "user_id": current_user.user.user_id,
        "report_id": report_id,
        "report_version": report_version,
        "path": path,
        "query": query,
        "allowed_param_names": allowed_param_names,
        "static_params": static_params,
        "exp": _get_token_expiry(current_user),
    }


def issue_report_query_token(
    *,
    current_user: CurrentUser,
    report_id: str,
    report_version: int,
    path: str,
    query: str,
    allowed_param_names: list[str],
    static_params: dict[str, Any],
) -> str:
    payload = _build_token_payload(
        current_user=current_user,
        report_id=report_id,
        report_version=report_version,
        path=path,
        query=query,
        allowed_param_names=allowed_param_names,
        static_params=static_params,
    )
    return _sign_payload(payload)


def build_report_query_capabilities(
    report_version: ReportVersion,
    current_user: CurrentUser,
) -> dict[str, str]:
    from reporting.schema import reporting_config

    try:
        report = reporting_config.Report.model_validate(report_version.config)
    except Exception:
        return {}
    capabilities: dict[str, str] = {}

    def add_capability(
        path: str,
        query: str | None,
        allowed_param_names: list[str],
        static_params: dict[str, Any],
    ) -> None:
        if query is None:
            return
        capabilities[path] = issue_report_query_token(
            current_user=current_user,
            report_id=report_version.report_id,
            report_version=report_version.version,
            path=path,
            query=query,
            allowed_param_names=allowed_param_names,
            static_params=static_params,
        )

    for input_index, input_def in enumerate(report.inputs):
        if input_def.cypher is None:
            continue
        add_capability(
            path=f"inputs.{input_index}.cypher",
            query=input_def.cypher,
            allowed_param_names=[],
            static_params={},
        )

    for row_index, row in enumerate(report.rows):
        for panel_index, panel in enumerate(row.panels):
            if panel.cypher is not None:
                add_capability(
                    path=f"rows.{row_index}.panels.{panel_index}.cypher",
                    query=report.queries.get(panel.cypher, panel.cypher),
                    allowed_param_names=[param.name for param in panel.params],
                    static_params={param.name: param.value for param in panel.params if param.value is not None},
                )
            if panel.details_cypher is not None:
                add_capability(
                    path=f"rows.{row_index}.panels.{panel_index}.details_cypher",
                    query=report.queries.get(panel.details_cypher, panel.details_cypher),
                    allowed_param_names=[param.name for param in panel.params],
                    static_params={param.name: param.value for param in panel.params if param.value is not None},
                )

    return capabilities


def resolve_report_query_request(
    *,
    token: str,
    current_user: CurrentUser,
    params: dict[str, Any] | None,
) -> tuple[str, dict[str, Any]]:
    payload = _verify_signed_token(token)

    if payload.get("kind") != _CAPABILITY_KIND:
        raise ValueError("Invalid report query token kind")
    if payload.get("v") != _CAPABILITY_VERSION:
        raise ValueError("Invalid report query token version")
    if payload.get("user_id") != current_user.user.user_id:
        raise PermissionError("Report query token does not belong to the current user")

    exp = payload.get("exp")
    if not isinstance(exp, int):
        raise ValueError("Invalid report query token expiry")
    if exp < int(time.time()):
        raise QueryTokenExpiredError("Report query token has expired")

    if not isinstance(payload.get("query"), str):
        raise ValueError("Invalid report query token payload")
    if not isinstance(payload.get("report_id"), str):
        raise ValueError("Invalid report query token payload")

    allowed_param_names = payload.get("allowed_param_names")
    static_params = payload.get("static_params")
    if not isinstance(allowed_param_names, list) or not all(isinstance(name, str) for name in allowed_param_names):
        raise ValueError("Invalid report query token payload")
    if not isinstance(static_params, dict):
        raise ValueError("Invalid report query token payload")

    request_params = params or {}
    unexpected = set(request_params) - set(allowed_param_names)
    if unexpected:
        raise ValueError(f"Unexpected query parameters: {', '.join(sorted(unexpected))}")

    merged_params = dict(static_params)
    for key, value in request_params.items():
        if key in static_params and static_params[key] != value:
            raise ValueError(f"Parameter mismatch for {key}")
        merged_params[key] = value

    return payload["query"], merged_params
