"""seed / export commands — bulk-load or dump YAML config via the Seizu API."""
import re
import sys
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from rich.console import Console

from seizu_cli import schema
from seizu_cli import state
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


def _list_reports() -> List[Dict[str, Any]]:
    return state.get_client().get("/api/v1/reports").get("reports", [])


def _get_report(report_id: str) -> Optional[Dict[str, Any]]:
    try:
        return state.get_client().get(f"/api/v1/reports/{report_id}")
    except APIError as exc:
        if exc.status_code == 404:
            return None
        raise


def _list_scheduled_queries() -> List[Dict[str, Any]]:
    return (
        state.get_client().get("/api/v1/scheduled-queries").get("scheduled_queries", [])
    )


def _sq_content_changed(
    existing: Dict[str, Any],
    resolved_cypher: str,
    params: List[Dict[str, Any]],
    frequency: Optional[int],
    watch_scans: List[Dict[str, Any]],
    enabled: bool,
    actions: List[Dict[str, Any]],
) -> bool:
    return (
        existing.get("cypher") != resolved_cypher
        or existing.get("params") != params
        or existing.get("frequency") != frequency
        or existing.get("watch_scans") != watch_scans
        or existing.get("enabled", True) != enabled
        or existing.get("actions") != actions
    )


def seed_cmd(config: str, force: bool, dry_run: bool) -> None:
    """Seed reports and scheduled queries from *config* YAML into the store via the API."""
    loaded = schema.load_file(config)

    if not loaded.reports and not loaded.scheduled_queries:
        console.print(
            "No reports or scheduled queries found in config file. Nothing to do."
        )
        return

    try:
        existing_list = _list_reports()
    except Exception as exc:
        _die(exc)
        return

    existing_by_name: Dict[str, Dict[str, Any]] = {r["name"]: r for r in existing_list}

    created = updated = skipped = 0
    seeded_ids: Dict[str, str] = {}

    for report_key, report in loaded.reports.items():
        report_config_dict = report.model_dump(exclude_none=True)
        existing = existing_by_name.get(report.name)

        if existing:
            if not force:
                latest = _get_report(existing["report_id"])
                if latest and latest.get("config") == report_config_dict:
                    console.print(
                        f"[dim][skip][/dim] '{report.name}' (config unchanged)"
                    )
                    skipped += 1
                    seeded_ids[report_key] = existing["report_id"]
                    continue

            if dry_run:
                console.print(
                    f"[yellow][dry-run][/yellow] would update report '{report.name}' (key: {report_key})"
                )
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
            console.print(
                f"[yellow][dry-run][/yellow] would create report '{report.name}' (key: {report_key})"
            )
            created += 1
            continue

        try:
            new_report = state.get_client().post(
                "/api/v1/reports", json={"name": report.name}
            )
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
            console.print(
                f"[green][dashboard][/green] set to '{dashboard_id}' (key: {loaded.dashboard})"
            )
        else:
            msg = (
                f"[yellow][warn][/yellow] dashboard key '{loaded.dashboard}'"
                " was not seeded, dashboard pointer not updated"
            )
            console.print(msg)

    console.print(f"\nReports: created={created} updated={updated} skipped={skipped}")
    console.print("\nSeeding scheduled queries...")
    _seed_scheduled_queries(loaded, force=force, dry_run=dry_run)

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
        existing_items: Dict[str, Dict[str, Any]] = {
            item["name"]: item for item in _list_scheduled_queries()
        }
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
        frequency: Optional[int] = sq.frequency

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
                console.print(
                    f"  [dim][skip][/dim] scheduled query '{sq.name}' (unchanged)"
                )
                skipped += 1
                continue
            if dry_run:
                console.print(
                    f"  [yellow][dry-run][/yellow] would update scheduled query '{sq.name}'"
                )
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
            console.print(
                f"  [blue][updated][/blue] '{existing['scheduled_query_id']}'  name='{sq.name}'"
            )
            updated += 1
            continue

        if dry_run:
            console.print(
                f"  [yellow][dry-run][/yellow] would create scheduled query '{sq.name}'"
            )
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
        console.print(
            f"  [green][created][/green] '{result['scheduled_query_id']}'  name='{sq.name}'"
        )
        created += 1

    console.print(
        f"  Scheduled queries: created={created} updated={updated} skipped={skipped}"
    )


def export_cmd(config: str, dry_run: bool) -> None:
    """Export latest report versions from the API back into *config* YAML."""
    try:
        existing_cfg = schema.load_file(config)
    except FileNotFoundError:
        err_console.print(
            f"[yellow][warn][/yellow] Config file '{config}' not found, starting from empty config."
        )
        existing_cfg = schema.ReportingConfig()

    name_to_key = {r.name: k for k, r in existing_cfg.reports.items()}

    try:
        report_list = _list_reports()
    except Exception as exc:
        _die(exc)
        return

    dashboard_id: Optional[str] = None
    try:
        dashboard_data = state.get_client().get("/api/v1/reports/dashboard")
        dashboard_id = dashboard_data.get("report_id")
    except APIError as exc:
        if exc.status_code != 404:
            err_console.print(
                f"[yellow][warn][/yellow] Could not fetch dashboard pointer: {exc}"
            )

    new_reports: Dict[str, Any] = {}
    dashboard_key: Optional[str] = None
    exported = failed = 0

    for item in sorted(report_list, key=lambda r: r["name"]):
        latest = _get_report(item["report_id"])
        if not latest:
            err_console.print(
                f"[yellow][warn][/yellow] No version found for '{item['name']}', skipping."
            )
            failed += 1
            continue

        try:
            report_obj = schema.Report.model_validate(latest["config"])
        except Exception as exc:
            err_console.print(
                f"[yellow][warn][/yellow] Invalid config for '{item['name']}': {exc} — skipping."
            )
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
        console.print(f"[green][export][/green] '{item['name']}' → key='{key}'")
        exported += 1

    updated_cfg = schema.ReportingConfig(
        queries=existing_cfg.queries,
        dashboard=dashboard_key
        if dashboard_key is not None
        else existing_cfg.dashboard,
        reports=new_reports,
        scheduled_queries=existing_cfg.scheduled_queries,
    )
    yaml_content = schema.dump_yaml(updated_cfg)

    if dry_run:
        console.print("\n--- YAML output (dry-run, not written) ---\n")
        console.print(yaml_content)
        console.print(
            f"\nDone. exported={exported} failed={failed} (dry-run, file not written)"
        )
        return

    with open(config, "w") as f:
        f.write(yaml_content)
    console.print(f"\nDone. exported={exported} failed={failed} → wrote '{config}'")
