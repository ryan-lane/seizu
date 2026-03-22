#!/usr/bin/env python3
"""Seed or export dashboard config using a YAML config file.

Subcommands
-----------
seed (default)
    Import reports and scheduled queries from a YAML file into the store.
    Reports: idempotent — existing reports whose latest version matches the
    YAML are skipped; changed ones get a new version.  Use ``--force`` to
    save a new version unconditionally.
    Scheduled queries: missing ones are created; existing ones are updated
    only if their content has changed.  Use ``--force`` to update all
    unconditionally.

export
    Export the latest version of every report from the store back into the
    YAML file.  The ``queries`` and ``scheduled_queries`` sections are
    preserved unchanged.  Existing YAML keys are reused when the report name
    matches; otherwise a slug derived from the name is used.  Use ``--dry-run``
    to print the resulting YAML without writing the file.

Usage (inside the seizu container)::

    # seed (default — no subcommand required)
    PYTHONPATH=/home/seizu/seizu pipenv run python scripts/seed_reports_from_yaml.py
    PYTHONPATH=/home/seizu/seizu pipenv run python scripts/seed_reports_from_yaml.py --config /path/to/other.yaml
    PYTHONPATH=/home/seizu/seizu pipenv run python scripts/seed_reports_from_yaml.py seed --force
    PYTHONPATH=/home/seizu/seizu pipenv run python scripts/seed_reports_from_yaml.py seed --dry-run

    # export
    PYTHONPATH=/home/seizu/seizu pipenv run python scripts/seed_reports_from_yaml.py export
    PYTHONPATH=/home/seizu/seizu pipenv run python scripts/seed_reports_from_yaml.py export --dry-run

Or via the Makefile shortcut::

    make seed_dashboard
    make seed_dashboard ARGS="seed --force"
    make seed_dashboard ARGS="seed --dry-run"
    make seed_dashboard ARGS="export"
    make seed_dashboard ARGS="export --dry-run"

Environment variables (all optional; defaults match docker-compose dev setup):

    DYNAMODB_TABLE_NAME      default: seizu-reports
    DYNAMODB_REGION          default: us-east-1
    DYNAMODB_ENDPOINT_URL    default: "" (use AWS default endpoint)
    DYNAMODB_CREATE_TABLE    default: false
    REPORTING_CONFIG_FILE    default: /reporting-dashboard.conf
    SNOWFLAKE_MACHINE_ID     default: 1
"""
import argparse
import re
import sys

from reporting import settings
from reporting.schema import reporting_config
from reporting.services import report_store


SEED_USER = "seed-script"
SEED_COMMENT = "Imported from YAML dashboard config"
SEED_UPDATE_COMMENT = "Updated from YAML dashboard config"


def _slugify(name: str) -> str:
    """Convert a report name into a YAML-friendly key (e.g. 'My Report' -> 'my-report')."""
    slug = name.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-") or "report"


def _existing_reports() -> dict:
    """Return a mapping of report name -> ReportListItem for all stored reports."""
    try:
        reports = report_store.list_reports()
        return {r.name: r for r in reports}
    except Exception as exc:
        print(f"[warn] Could not fetch existing reports: {exc}", file=sys.stderr)
        return {}


def seed(config_file: str, force: bool, dry_run: bool) -> None:
    config = reporting_config.load_file(config_file)

    if settings.DYNAMODB_CREATE_TABLE and not dry_run:
        report_store.initialize()

    if not config.reports and not config.scheduled_queries:
        print("No reports or scheduled queries found in config file. Nothing to do.")
        return

    existing = _existing_reports()

    created = 0
    updated = 0
    skipped = 0
    # Maps yaml key -> seeded/updated report_id, used to resolve the dashboard pointer.
    seeded_ids: dict = {}

    for report_id_key, report in config.reports.items():
        report_config_dict = report.model_dump()

        existing_item = existing.get(report.name)
        if existing_item and not force:
            # Compare YAML config against the latest stored version.
            latest = report_store.get_report_latest(existing_item.report_id)
            if latest and latest.config == report_config_dict:
                print(f"[skip] '{report.name}' (config unchanged)")
                skipped += 1
                seeded_ids[report_id_key] = existing_item.report_id
                continue

            # Config has changed (or latest version not found) — save a new version.
            if dry_run:
                print(
                    f"[dry-run] would update report '{report.name}'"
                    f" (key: {report_id_key})"
                )
                updated += 1
                seeded_ids[report_id_key] = existing_item.report_id
                continue

            report_store.save_report_version(
                report_id=existing_item.report_id,
                config=report_config_dict,
                created_by=SEED_USER,
                comment=SEED_UPDATE_COMMENT,
            )
            seeded_ids[report_id_key] = existing_item.report_id
            print(
                f"[updated] '{existing_item.report_id}' name='{report.name}'"
                f" yaml_key='{report_id_key}'"
            )
            updated += 1
            continue

        if dry_run:
            print(
                f"[dry-run] would create report '{report.name}' (key: {report_id_key})"
            )
            created += 1
            continue

        result = report_store.create_report(
            name=report.name,
            created_by=SEED_USER,
        )
        report_store.save_report_version(
            report_id=result.report_id,
            config=report_config_dict,
            created_by=SEED_USER,
            comment=SEED_COMMENT,
        )
        seeded_ids[report_id_key] = result.report_id
        print(
            f"[created] '{result.report_id}' name='{report.name}'"
            f" yaml_key='{report_id_key}'"
        )
        created += 1

    if config.dashboard and not dry_run:
        dashboard_report_id = seeded_ids.get(config.dashboard)
        if dashboard_report_id:
            report_store.set_dashboard_report(dashboard_report_id)
            print(
                f"[dashboard] set to '{dashboard_report_id}' (key: {config.dashboard})"
            )
        else:
            print(
                f"[warn] dashboard key '{config.dashboard}' was not seeded"
                " (already existed or not found); dashboard pointer not updated"
            )

    print(f"\nReports: created={created} updated={updated} skipped={skipped}")

    print("\nSeeding scheduled queries...")
    seed_scheduled_queries(config, force=force, dry_run=dry_run)

    if dry_run:
        print("\n(dry-run, no writes performed)")


def _sq_content_changed(  # type: ignore
    existing, resolved_cypher, params, frequency, watch_scans, enabled, actions
) -> bool:
    """Return True if any content field differs from what is stored."""
    return (
        existing.cypher != resolved_cypher
        or existing.params != params
        or existing.frequency != frequency
        or existing.watch_scans != watch_scans
        or existing.enabled != enabled
        or existing.actions != actions
    )


def seed_scheduled_queries(
    config: "reporting_config.ReportingConfig", force: bool, dry_run: bool
) -> None:
    """Seed scheduled queries from a loaded config into the store.

    Missing queries are always created.  Existing ones are updated only when
    their content has changed (or when ``force`` is True).
    """
    if not config.scheduled_queries:
        print("  No scheduled queries in config, skipping.")
        return

    # Build a name -> existing item map
    try:
        existing_items = {
            item.name: item for item in report_store.list_scheduled_queries()
        }
    except Exception as exc:
        print(
            f"[warn] Could not fetch existing scheduled queries: {exc}", file=sys.stderr
        )
        existing_items = {}

    created = 0
    updated = 0
    skipped = 0

    for sq in config.scheduled_queries:
        # Resolve cypher reference against the top-level queries dict
        resolved_cypher = config.queries.get(sq.cypher, sq.cypher)
        params = [p.model_dump() for p in sq.params]
        watch_scans = [ws.model_dump() for ws in sq.watch_scans]
        actions = [a.model_dump() for a in sq.actions]
        enabled = sq.enabled if sq.enabled is not None else True

        existing = existing_items.get(sq.name)

        if existing:
            changed = force or _sq_content_changed(
                existing,
                resolved_cypher,
                params,
                sq.frequency,
                watch_scans,
                enabled,
                actions,
            )
            if not changed:
                print(f"  [skip] scheduled query '{sq.name}' (unchanged)")
                skipped += 1
                continue
            if dry_run:
                print(f"  [dry-run] would update scheduled query '{sq.name}'")
                updated += 1
                continue
            report_store.update_scheduled_query(
                sq_id=existing.scheduled_query_id,
                name=sq.name,
                cypher=resolved_cypher,
                params=params,
                frequency=sq.frequency,
                watch_scans=watch_scans,
                enabled=enabled,
                actions=actions,
                updated_by=SEED_USER,
                comment=SEED_UPDATE_COMMENT,
            )
            print(
                f"  [updated] scheduled query '{existing.scheduled_query_id}' name='{sq.name}'"
            )
            updated += 1
            continue

        if dry_run:
            print(f"  [dry-run] would create scheduled query '{sq.name}'")
            created += 1
            continue

        result = report_store.create_scheduled_query(
            name=sq.name,
            cypher=resolved_cypher,
            params=params,
            frequency=sq.frequency,
            watch_scans=watch_scans,
            enabled=enabled,
            actions=actions,
            created_by=SEED_USER,
        )
        print(
            f"  [created] scheduled query '{result.scheduled_query_id}' name='{sq.name}'"
        )
        created += 1

    print(f"  Scheduled queries: created={created} updated={updated} skipped={skipped}")


def export_cmd(config_file: str, dry_run: bool) -> None:
    """Export latest report versions from the store into the YAML config file."""
    # Load existing config so we can preserve queries and scheduled_queries.
    try:
        existing_config = reporting_config.load_file(config_file)
    except FileNotFoundError:
        print(
            f"[warn] Config file '{config_file}' not found, starting from empty config.",
            file=sys.stderr,
        )
        existing_config = reporting_config.ReportingConfig()

    # Build a name -> YAML key map from the current file so existing keys are reused.
    name_to_key = {r.name: k for k, r in existing_config.reports.items()}

    try:
        report_list = report_store.list_reports()
    except Exception as exc:
        print(f"[error] Could not fetch reports: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        dashboard_id = report_store.get_dashboard_report_id()
    except Exception:
        dashboard_id = None

    new_reports: dict = {}
    dashboard_key = None
    exported = 0
    failed = 0

    for item in sorted(report_list, key=lambda r: r.name):
        latest = report_store.get_report_latest(item.report_id)
        if not latest:
            print(
                f"[warn] No version found for '{item.name}', skipping.",
                file=sys.stderr,
            )
            failed += 1
            continue

        try:
            report_obj = reporting_config.Report.model_validate(latest.config)
        except Exception as exc:
            print(
                f"[warn] Invalid config for '{item.name}': {exc} -- skipping.",
                file=sys.stderr,
            )
            failed += 1
            continue

        key = name_to_key.get(item.name) or _slugify(item.name)
        # Ensure key uniqueness if two different names slug to the same value.
        base_key = key
        suffix = 2
        while key in new_reports and new_reports[key].name != item.name:
            key = f"{base_key}-{suffix}"
            suffix += 1

        new_reports[key] = report_obj
        if dashboard_id and item.report_id == dashboard_id:
            dashboard_key = key
        print(f"[export] '{item.name}' -> key='{key}'")
        exported += 1

    updated = reporting_config.ReportingConfig(
        queries=existing_config.queries,
        dashboard=dashboard_key
        if dashboard_key is not None
        else existing_config.dashboard,
        reports=new_reports,
        scheduled_queries=existing_config.scheduled_queries,
    )
    yaml_content = reporting_config.dump_yaml(updated)

    if dry_run:
        print("\n--- YAML output (dry-run, not written) ---\n")
        print(yaml_content)
        print(
            f"\nDone. exported={exported} failed={failed} (dry-run, file not written)"
        )
        return

    with open(config_file, "w") as f:
        f.write(yaml_content)
    print(f"\nDone. exported={exported} failed={failed} -> wrote '{config_file}'")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed or export DynamoDB reports using a YAML dashboard config file.",
    )
    parser.add_argument(
        "--config",
        default=settings.REPORTING_CONFIG_FILE,
        help=(
            "Path to the YAML dashboard config file "
            f"(default: {settings.REPORTING_CONFIG_FILE})"
        ),
    )

    subparsers = parser.add_subparsers(dest="command")

    seed_parser = subparsers.add_parser(
        "seed",
        help="Import reports and scheduled queries from the YAML file (default action).",
    )
    seed_parser.add_argument(
        "--force",
        action="store_true",
        help="Update existing records even if content is unchanged.",
    )
    seed_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be created without writing anything to the store.",
    )

    export_parser = subparsers.add_parser(
        "export",
        help="Export latest report versions from the store back into the YAML file.",
    )
    export_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the resulting YAML without overwriting the config file.",
    )

    args = parser.parse_args()

    if args.command == "export":
        export_cmd(config_file=args.config, dry_run=args.dry_run)
    else:
        # Default to seed (supports being called with no subcommand for backwards compat,
        # or explicitly as `seed --force` / `seed --dry-run`).
        force = getattr(args, "force", False)
        dry_run = getattr(args, "dry_run", False)
        seed(config_file=args.config, force=force, dry_run=dry_run)


if __name__ == "__main__":
    main()
