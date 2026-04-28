"""Built-in ``reports__*`` tools — CRUD + pin/dashboard for reports."""

from typing import Any

from reporting.authnz import CurrentUser
from reporting.authnz.permissions import Permission
from reporting.schema.report_config import (
    CloneReportRequest,
    CreateReportRequest,
    CreateVersionRequest,
    PinReportRequest,
)
from reporting.services import report_store
from reporting.services.mcp_builtins.base import BuiltinGroup, BuiltinTool, model_input_schema

GROUP = "reports"


def _require_user(current_user: CurrentUser | None) -> CurrentUser:
    if current_user is None:
        raise RuntimeError("No current user on the request context")
    return current_user


def _report_id_prop() -> dict[str, Any]:
    return {"report_id": {"type": "string", "description": "The report ID."}}


async def _list(args: dict[str, Any], current_user: CurrentUser | None) -> dict[str, Any]:
    reports = await report_store.list_reports()
    return {"reports": [r.model_dump() for r in reports]}


async def _get(args: dict[str, Any], current_user: CurrentUser | None) -> dict[str, Any]:
    report = await report_store.get_report_latest(args["report_id"])
    if not report:
        return {"error": "Report not found"}
    return report.model_dump()


async def _get_dashboard(args: dict[str, Any], current_user: CurrentUser | None) -> dict[str, Any]:
    report = await report_store.get_dashboard_report()
    if not report:
        return {"error": "No dashboard report configured"}
    return report.model_dump()


async def _create(args: dict[str, Any], current_user: CurrentUser | None) -> dict[str, Any]:
    user = _require_user(current_user)
    body = CreateReportRequest.model_validate(args)
    item = await report_store.create_report(name=body.name, created_by=user.user.user_id)
    return item.model_dump()


async def _create_version(args: dict[str, Any], current_user: CurrentUser | None) -> dict[str, Any]:
    user = _require_user(current_user)
    report_id = args["report_id"]
    body = CreateVersionRequest.model_validate({k: v for k, v in args.items() if k != "report_id"})
    version = await report_store.save_report_version(
        report_id=report_id,
        config=body.config,
        created_by=user.user.user_id,
        comment=body.comment,
    )
    if not version:
        return {"error": "Report not found"}
    return version.model_dump()


async def _delete(args: dict[str, Any], current_user: CurrentUser | None) -> dict[str, Any]:
    ok = await report_store.delete_report(args["report_id"])
    if not ok:
        return {"error": "Report not found"}
    return {"report_id": args["report_id"]}


async def _pin(args: dict[str, Any], current_user: CurrentUser | None) -> dict[str, Any]:
    report_id = args["report_id"]
    body = PinReportRequest.model_validate({k: v for k, v in args.items() if k != "report_id"})
    ok = await report_store.pin_report(report_id, body.pinned)
    if not ok:
        return {"error": "Report not found"}
    return {"report_id": report_id, "pinned": body.pinned}


async def _set_dashboard(args: dict[str, Any], current_user: CurrentUser | None) -> dict[str, Any]:
    ok = await report_store.set_dashboard_report(args["report_id"])
    if not ok:
        return {"error": "Report not found"}
    return {"report_id": args["report_id"]}


async def _list_versions(args: dict[str, Any], current_user: CurrentUser | None) -> dict[str, Any]:
    versions = await report_store.list_report_versions(args["report_id"])
    if not versions:
        return {"error": "Report not found"}
    return {"versions": [v.model_dump() for v in versions]}


async def _get_version(args: dict[str, Any], current_user: CurrentUser | None) -> dict[str, Any]:
    version = await report_store.get_report_version(args["report_id"], int(args["version"]))
    if not version:
        return {"error": "Version not found"}
    return version.model_dump()


async def _clone(args: dict[str, Any], current_user: CurrentUser | None) -> dict[str, Any]:
    user = _require_user(current_user)
    source = await report_store.get_report_latest(args["report_id"])
    if not source:
        return {"error": "Report not found"}
    body = CloneReportRequest.model_validate({k: v for k, v in args.items() if k != "report_id"})
    new_item = await report_store.create_report(name=body.name, created_by=user.user.user_id)
    await report_store.save_report_version(
        report_id=new_item.report_id,
        config=source.config,
        created_by=user.user.user_id,
        comment=f"Cloned from {source.name}",
    )
    return new_item.model_dump()


GROUP_DEF = BuiltinGroup(
    name=GROUP,
    tools=[
        BuiltinTool(
            name="reports__list",
            group=GROUP,
            description="List all reports (metadata only).",
            input_schema={"type": "object", "properties": {}},
            required_permissions=[Permission.REPORTS_READ.value],
            handler=_list,
        ),
        BuiltinTool(
            name="reports__get",
            group=GROUP,
            description="Return the latest version of a report.",
            input_schema={
                "type": "object",
                "properties": _report_id_prop(),
                "required": ["report_id"],
            },
            required_permissions=[Permission.REPORTS_READ.value],
            handler=_get,
        ),
        BuiltinTool(
            name="reports__get_dashboard",
            group=GROUP,
            description="Return the latest version of the default dashboard report.",
            input_schema={"type": "object", "properties": {}},
            required_permissions=[Permission.REPORTS_READ.value],
            handler=_get_dashboard,
        ),
        BuiltinTool(
            name="reports__create",
            group=GROUP,
            description="Create a new report.",
            input_schema=model_input_schema(CreateReportRequest),
            required_permissions=[Permission.REPORTS_WRITE.value],
            handler=_create,
            requires_user=True,
        ),
        BuiltinTool(
            name="reports__create_version",
            group=GROUP,
            description="Save a new version of an existing report.",
            input_schema=model_input_schema(
                CreateVersionRequest,
                extra_properties=_report_id_prop(),
                extra_required=["report_id"],
            ),
            required_permissions=[Permission.REPORTS_WRITE.value],
            handler=_create_version,
            requires_user=True,
        ),
        BuiltinTool(
            name="reports__delete",
            group=GROUP,
            description="Delete a report and all its versions.",
            input_schema={
                "type": "object",
                "properties": _report_id_prop(),
                "required": ["report_id"],
            },
            required_permissions=[Permission.REPORTS_DELETE.value],
            handler=_delete,
        ),
        BuiltinTool(
            name="reports__pin",
            group=GROUP,
            description="Pin or unpin a report on the dashboard nav.",
            input_schema=model_input_schema(
                PinReportRequest,
                extra_properties=_report_id_prop(),
                extra_required=["report_id"],
            ),
            required_permissions=[Permission.REPORTS_WRITE.value],
            handler=_pin,
        ),
        BuiltinTool(
            name="reports__set_dashboard",
            group=GROUP,
            description="Set the given report as the default dashboard.",
            input_schema={
                "type": "object",
                "properties": _report_id_prop(),
                "required": ["report_id"],
            },
            required_permissions=[Permission.REPORTS_SET_DASHBOARD.value],
            handler=_set_dashboard,
        ),
        BuiltinTool(
            name="reports__list_versions",
            group=GROUP,
            description="List all versions of a report.",
            input_schema={
                "type": "object",
                "properties": _report_id_prop(),
                "required": ["report_id"],
            },
            required_permissions=[Permission.REPORTS_READ.value],
            handler=_list_versions,
        ),
        BuiltinTool(
            name="reports__get_version",
            group=GROUP,
            description="Return a specific version of a report.",
            input_schema={
                "type": "object",
                "properties": {
                    **_report_id_prop(),
                    "version": {
                        "type": "integer",
                        "description": "The version number.",
                    },
                },
                "required": ["report_id", "version"],
            },
            required_permissions=[Permission.REPORTS_READ.value],
            handler=_get_version,
        ),
        BuiltinTool(
            name="reports__clone",
            group=GROUP,
            description="Clone a report into a new report with the given name.",
            input_schema=model_input_schema(
                CloneReportRequest,
                extra_properties=_report_id_prop(),
                extra_required=["report_id"],
            ),
            required_permissions=[Permission.REPORTS_WRITE.value],
            handler=_clone,
            requires_user=True,
        ),
    ],
)
