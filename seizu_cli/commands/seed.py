"""seed / export commands — bulk-load or dump YAML config via the Seizu API."""

import re
import sys
from typing import Any

from rich.console import Console

from seizu_cli import schema, state
from seizu_cli.client import APIError

console = Console()
err_console = Console(stderr=True)

SEED_COMMENT = "Imported from YAML dashboard config"
SEED_UPDATE_COMMENT = "Updated from YAML dashboard config"


def _slugify(name: str) -> str:
    slug = name.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-") or "report"


def _die(exc: Exception) -> None:
    if isinstance(exc, APIError):
        err_console.print(f"[red]Error {exc.status_code}[/red]: {exc}")
    else:
        err_console.print(f"[red]Error[/red]: {exc}")
    sys.exit(1)


def _list_reports() -> list[dict[str, Any]]:
    return state.get_client().get("/api/v1/reports").get("reports", [])


def _get_report(report_id: str) -> dict[str, Any] | None:
    try:
        return state.get_client().get(f"/api/v1/reports/{report_id}")
    except APIError as exc:
        if exc.status_code == 404:
            return None
        raise


def _list_scheduled_queries() -> list[dict[str, Any]]:
    return state.get_client().get("/api/v1/scheduled-queries").get("scheduled_queries", [])


def _sq_content_changed(
    existing: dict[str, Any],
    resolved_cypher: str,
    params: list[dict[str, Any]],
    frequency: int | None,
    watch_scans: list[dict[str, Any]],
    enabled: bool,
    actions: list[dict[str, Any]],
) -> bool:
    return (
        existing.get("cypher") != resolved_cypher
        or existing.get("params") != params
        or existing.get("frequency") != frequency
        or existing.get("watch_scans") != watch_scans
        or existing.get("enabled", True) != enabled
        or existing.get("actions") != actions
    )


def _list_toolsets() -> list[dict[str, Any]]:
    return state.get_client().get("/api/v1/toolsets").get("toolsets", [])


def _list_tools(toolset_id: str) -> list[dict[str, Any]]:
    return state.get_client().get(f"/api/v1/toolsets/{toolset_id}/tools").get("tools", [])


def _toolset_content_changed(
    existing: dict[str, Any],
    name: str,
    description: str,
    enabled: bool,
) -> bool:
    return (
        existing.get("name") != name
        or existing.get("description", "") != description
        or existing.get("enabled", True) != enabled
    )


def _tool_content_changed(
    existing: dict[str, Any],
    name: str,
    description: str,
    cypher: str,
    parameters: list[dict[str, Any]],
    enabled: bool,
) -> bool:
    return (
        existing.get("name") != name
        or existing.get("description", "") != description
        or existing.get("cypher") != cypher
        or existing.get("parameters", []) != parameters
        or existing.get("enabled", True) != enabled
    )


def seed_cmd(config: str, force: bool, dry_run: bool) -> None:
    """Seed reports, scheduled queries, and toolsets from *config* YAML into the store via the API."""
    loaded = schema.load_file(config)

    if not loaded.reports and not loaded.scheduled_queries and not loaded.toolsets:
        console.print("No reports, scheduled queries, or toolsets found in config file. Nothing to do.")
        return

    try:
        existing_list = _list_reports()
    except Exception as exc:
        _die(exc)
        return

    existing_by_name: dict[str, dict[str, Any]] = {r["name"]: r for r in existing_list}

    created = updated = skipped = 0
    seeded_ids: dict[str, str] = {}

    for report_key, report in loaded.reports.items():
        report_config_dict = report.model_dump(exclude_none=True)
        existing = existing_by_name.get(report.name)

        if existing:
            if not force:
                latest = _get_report(existing["report_id"])
                if latest and latest.get("config") == report_config_dict:
                    console.print(f"[dim][skip][/dim] '{report.name}' (config unchanged)")
                    skipped += 1
                    seeded_ids[report_key] = existing["report_id"]
                    continue

            if dry_run:
                console.print(f"[yellow][dry-run][/yellow] would update report '{report.name}' (key: {report_key})")
                updated += 1
                seeded_ids[report_key] = existing["report_id"]
                continue

            try:
                state.get_client().post(
                    f"/api/v1/reports/{existing['report_id']}/versions",
                    json={"config": report_config_dict, "comment": SEED_UPDATE_COMMENT},
                )
            except Exception as exc:
                _die(exc)
                return
            seeded_ids[report_key] = existing["report_id"]
            console.print(
                f"[blue][updated][/blue] '{existing['report_id']}'  name='{report.name}'  yaml_key='{report_key}'"
            )
            updated += 1
            continue

        if dry_run:
            console.print(f"[yellow][dry-run][/yellow] would create report '{report.name}' (key: {report_key})")
            created += 1
            continue

        try:
            new_report = state.get_client().post("/api/v1/reports", json={"name": report.name})
            state.get_client().post(
                f"/api/v1/reports/{new_report['report_id']}/versions",
                json={"config": report_config_dict, "comment": SEED_COMMENT},
            )
        except Exception as exc:
            _die(exc)
            return

        seeded_ids[report_key] = new_report["report_id"]
        console.print(
            f"[green][created][/green] '{new_report['report_id']}'  name='{report.name}'  yaml_key='{report_key}'"
        )
        created += 1

    if loaded.dashboard and not dry_run:
        dashboard_id = seeded_ids.get(loaded.dashboard)
        if dashboard_id:
            try:
                state.get_client().put(f"/api/v1/reports/{dashboard_id}/dashboard")
            except Exception as exc:
                _die(exc)
                return
            console.print(f"[green][dashboard][/green] set to '{dashboard_id}' (key: {loaded.dashboard})")
        else:
            msg = (
                f"[yellow][warn][/yellow] dashboard key '{loaded.dashboard}'"
                " was not seeded, dashboard pointer not updated"
            )
            console.print(msg)

    console.print(f"\nReports: created={created} updated={updated} skipped={skipped}")
    console.print("\nSeeding scheduled queries...")
    _seed_scheduled_queries(loaded, force=force, dry_run=dry_run)

    console.print("\nSeeding toolsets...")
    _seed_toolsets(loaded, force=force, dry_run=dry_run)

    if dry_run:
        console.print("\n(dry-run, no writes performed)")


def _seed_scheduled_queries(
    config: Any,
    force: bool,
    dry_run: bool,
) -> None:
    if not config.scheduled_queries:
        console.print("  No scheduled queries in config, skipping.")
        return

    try:
        existing_items: dict[str, dict[str, Any]] = {item["name"]: item for item in _list_scheduled_queries()}
    except Exception as exc:
        _die(exc)
        return

    created = updated = skipped = 0

    for sq in config.scheduled_queries:
        resolved_cypher: str = config.queries.get(sq.cypher, sq.cypher)
        params = [p.model_dump() for p in sq.params]
        watch_scans = [ws.model_dump() for ws in sq.watch_scans]
        actions = [a.model_dump() for a in sq.actions]
        enabled = sq.enabled if sq.enabled is not None else True
        frequency: int | None = sq.frequency

        existing = existing_items.get(sq.name)

        if existing:
            changed = force or _sq_content_changed(
                existing,
                resolved_cypher,
                params,
                frequency,
                watch_scans,
                enabled,
                actions,
            )
            if not changed:
                console.print(f"  [dim][skip][/dim] scheduled query '{sq.name}' (unchanged)")
                skipped += 1
                continue
            if dry_run:
                console.print(f"  [yellow][dry-run][/yellow] would update scheduled query '{sq.name}'")
                updated += 1
                continue
            try:
                state.get_client().put(
                    f"/api/v1/scheduled-queries/{existing['scheduled_query_id']}",
                    json={
                        "name": sq.name,
                        "cypher": resolved_cypher,
                        "params": params,
                        "frequency": frequency,
                        "watch_scans": watch_scans,
                        "enabled": enabled,
                        "actions": actions,
                        "comment": SEED_UPDATE_COMMENT,
                    },
                )
            except Exception as exc:
                _die(exc)
                return
            console.print(f"  [blue][updated][/blue] '{existing['scheduled_query_id']}'  name='{sq.name}'")
            updated += 1
            continue

        if dry_run:
            console.print(f"  [yellow][dry-run][/yellow] would create scheduled query '{sq.name}'")
            created += 1
            continue

        try:
            result = state.get_client().post(
                "/api/v1/scheduled-queries",
                json={
                    "name": sq.name,
                    "cypher": resolved_cypher,
                    "params": params,
                    "frequency": frequency,
                    "watch_scans": watch_scans,
                    "enabled": enabled,
                    "actions": actions,
                },
            )
        except Exception as exc:
            _die(exc)
            return
        console.print(f"  [green][created][/green] '{result['scheduled_query_id']}'  name='{sq.name}'")
        created += 1

    console.print(f"  Scheduled queries: created={created} updated={updated} skipped={skipped}")


def _seed_toolsets(
    config: Any,
    force: bool,
    dry_run: bool,
) -> None:
    if not config.toolsets:
        console.print("  No toolsets in config, skipping.")
        return

    try:
        existing_toolsets: dict[str, dict[str, Any]] = {item["name"]: item for item in _list_toolsets()}
    except Exception as exc:
        _die(exc)
        return

    ts_created = ts_updated = ts_skipped = 0

    for ts_key, ts_def in config.toolsets.items():
        existing_ts = existing_toolsets.get(ts_def.name)
        description = ts_def.description or ""
        enabled = ts_def.enabled if ts_def.enabled is not None else True

        if existing_ts:
            changed = force or _toolset_content_changed(existing_ts, ts_def.name, description, enabled)
            if not changed:
                console.print(f"  [dim][skip][/dim] toolset '{ts_def.name}' (unchanged)")
                ts_skipped += 1
                toolset_id = existing_ts["toolset_id"]
            elif dry_run:
                console.print(f"  [yellow][dry-run][/yellow] would update toolset '{ts_def.name}' (key: {ts_key})")
                ts_updated += 1
                toolset_id = existing_ts["toolset_id"]
            else:
                try:
                    state.get_client().put(
                        f"/api/v1/toolsets/{existing_ts['toolset_id']}",
                        json={
                            "name": ts_def.name,
                            "description": description,
                            "enabled": enabled,
                            "comment": SEED_UPDATE_COMMENT,
                        },
                    )
                except Exception as exc:
                    _die(exc)
                    return
                console.print(
                    f"  [blue][updated][/blue] '{existing_ts['toolset_id']}'  name='{ts_def.name}'  yaml_key='{ts_key}'"
                )
                ts_updated += 1
                toolset_id = existing_ts["toolset_id"]
        elif dry_run:
            console.print(f"  [yellow][dry-run][/yellow] would create toolset '{ts_def.name}' (key: {ts_key})")
            ts_created += 1
            toolset_id = None
        else:
            try:
                result = state.get_client().post(
                    "/api/v1/toolsets",
                    json={
                        "name": ts_def.name,
                        "description": description,
                        "enabled": enabled,
                    },
                )
            except Exception as exc:
                _die(exc)
                return
            console.print(
                f"  [green][created][/green] '{result['toolset_id']}'  name='{ts_def.name}'  yaml_key='{ts_key}'"
            )
            ts_created += 1
            toolset_id = result["toolset_id"]

        if toolset_id is None or not ts_def.tools:
            continue

        try:
            existing_tools: dict[str, dict[str, Any]] = {t["name"]: t for t in _list_tools(toolset_id)}
        except Exception as exc:
            _die(exc)
            return

        for tool_key, tool_def in ts_def.tools.items():
            tool_description = tool_def.description or ""
            tool_enabled = tool_def.enabled if tool_def.enabled is not None else True
            tool_params = [p.model_dump() for p in tool_def.parameters]
            existing_tool = existing_tools.get(tool_def.name)

            if existing_tool:
                tool_changed = force or _tool_content_changed(
                    existing_tool,
                    tool_def.name,
                    tool_description,
                    tool_def.cypher,
                    tool_params,
                    tool_enabled,
                )
                if not tool_changed:
                    console.print(f"    [dim][skip][/dim] tool '{tool_def.name}' (unchanged)")
                elif dry_run:
                    console.print(
                        f"    [yellow][dry-run][/yellow] would update tool '{tool_def.name}' (key: {tool_key})"
                    )
                else:
                    try:
                        state.get_client().put(
                            f"/api/v1/toolsets/{toolset_id}/tools/{existing_tool['tool_id']}",
                            json={
                                "name": tool_def.name,
                                "description": tool_description,
                                "cypher": tool_def.cypher,
                                "parameters": tool_params,
                                "enabled": tool_enabled,
                                "comment": SEED_UPDATE_COMMENT,
                            },
                        )
                    except Exception as exc:
                        _die(exc)
                        return
                    console.print(
                        f"    [blue][updated][/blue] '{existing_tool['tool_id']}'"
                        f"  name='{tool_def.name}'  yaml_key='{tool_key}'"
                    )
            elif dry_run:
                console.print(f"    [yellow][dry-run][/yellow] would create tool '{tool_def.name}' (key: {tool_key})")
            else:
                try:
                    result = state.get_client().post(
                        f"/api/v1/toolsets/{toolset_id}/tools",
                        json={
                            "name": tool_def.name,
                            "description": tool_description,
                            "cypher": tool_def.cypher,
                            "parameters": tool_params,
                            "enabled": tool_enabled,
                        },
                    )
                except Exception as exc:
                    _die(exc)
                    return
                console.print(
                    f"    [green][created][/green] '{result['tool_id']}'  name='{tool_def.name}'  yaml_key='{tool_key}'"
                )

    console.print(f"  Toolsets: created={ts_created} updated={ts_updated} skipped={ts_skipped}")


def export_cmd(config: str, dry_run: bool) -> None:
    """Export latest report versions and toolsets from the API back into *config* YAML."""
    try:
        existing_cfg = schema.load_file(config)
    except FileNotFoundError:
        err_console.print(f"[yellow][warn][/yellow] Config file '{config}' not found, starting from empty config.")
        existing_cfg = schema.ReportingConfig()

    name_to_key = {r.name: k for k, r in existing_cfg.reports.items()}

    try:
        report_list = _list_reports()
    except Exception as exc:
        _die(exc)
        return

    dashboard_id: str | None = None
    try:
        dashboard_data = state.get_client().get("/api/v1/reports/dashboard")
        dashboard_id = dashboard_data.get("report_id")
    except APIError as exc:
        if exc.status_code != 404:
            err_console.print(f"[yellow][warn][/yellow] Could not fetch dashboard pointer: {exc}")

    new_reports: dict[str, Any] = {}
    dashboard_key: str | None = None
    exported = failed = 0

    for item in sorted(report_list, key=lambda r: r["name"]):
        latest = _get_report(item["report_id"])
        if not latest:
            err_console.print(f"[yellow][warn][/yellow] No version found for '{item['name']}', skipping.")
            failed += 1
            continue

        try:
            report_obj = schema.Report.model_validate(latest["config"])
        except Exception as exc:
            err_console.print(f"[yellow][warn][/yellow] Invalid config for '{item['name']}': {exc} — skipping.")
            failed += 1
            continue

        key = name_to_key.get(item["name"]) or _slugify(item["name"])
        base_key = key
        suffix = 2
        while key in new_reports and new_reports[key].name != item["name"]:
            key = f"{base_key}-{suffix}"
            suffix += 1

        new_reports[key] = report_obj
        if dashboard_id and item["report_id"] == dashboard_id:
            dashboard_key = key
        console.print(f"[green][export][/green] report '{item['name']}' → key='{key}'")
        exported += 1

    # Export toolsets
    ts_name_to_key = {ts.name: k for k, ts in existing_cfg.toolsets.items()}
    new_toolsets: dict[str, Any] = {}
    ts_exported = ts_failed = 0

    try:
        toolset_list = _list_toolsets()
    except Exception as exc:
        _die(exc)
        return

    for ts_item in sorted(toolset_list, key=lambda t: t["name"]):
        ts_key = ts_name_to_key.get(ts_item["name"]) or _slugify(ts_item["name"])
        base_key = ts_key
        suffix = 2
        while ts_key in new_toolsets and new_toolsets[ts_key].name != ts_item["name"]:
            ts_key = f"{base_key}-{suffix}"
            suffix += 1

        tool_key_by_name: dict[str, str] = {}
        if ts_item["name"] in existing_cfg.toolsets:
            existing_ts_def = existing_cfg.toolsets[ts_name_to_key[ts_item["name"]]]
            tool_key_by_name = {td.name: tk for tk, td in existing_ts_def.tools.items()}

        try:
            tools_data = _list_tools(ts_item["toolset_id"])
        except Exception as exc:
            err_console.print(
                f"[yellow][warn][/yellow] Could not fetch tools for '{ts_item['name']}': {exc} — skipping toolset."
            )
            ts_failed += 1
            continue

        new_tools: dict[str, Any] = {}
        for tool in sorted(tools_data, key=lambda t: t["name"]):
            tool_key = tool_key_by_name.get(tool["name"]) or _slugify(tool["name"])
            base_tool_key = tool_key
            suffix = 2
            while tool_key in new_tools and new_tools[tool_key].name != tool["name"]:
                tool_key = f"{base_tool_key}-{suffix}"
                suffix += 1
            params = [schema.ToolParamDef.model_validate(p) for p in tool.get("parameters", [])]
            new_tools[tool_key] = schema.ToolDef(
                name=tool["name"],
                description=tool.get("description", ""),
                cypher=tool["cypher"],
                parameters=params,
                enabled=tool.get("enabled", True),
            )

        new_toolsets[ts_key] = schema.ToolsetDef(
            name=ts_item["name"],
            description=ts_item.get("description", ""),
            enabled=ts_item.get("enabled", True),
            tools=new_tools,
        )
        console.print(f"[green][export][/green] toolset '{ts_item['name']}' ({len(new_tools)} tools) → key='{ts_key}'")
        ts_exported += 1

    updated_cfg = schema.ReportingConfig(
        queries=existing_cfg.queries,
        dashboard=dashboard_key if dashboard_key is not None else existing_cfg.dashboard,
        reports=new_reports,
        scheduled_queries=existing_cfg.scheduled_queries,
        toolsets=new_toolsets,
    )
    yaml_content = schema.dump_yaml(updated_cfg)

    if dry_run:
        console.print("\n--- YAML output (dry-run, not written) ---\n")
        console.print(yaml_content)
        console.print(
            f"\nDone. reports: exported={exported} failed={failed}  "
            f"toolsets: exported={ts_exported} failed={ts_failed}  "
            "(dry-run, file not written)"
        )
        return

    with open(config, "w") as f:
        f.write(yaml_content)
    console.print(
        f"\nDone. reports: exported={exported} failed={failed}  "
        f"toolsets: exported={ts_exported} failed={ts_failed}  "
        f"→ wrote '{config}'"
    )
