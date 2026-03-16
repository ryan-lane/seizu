#!/usr/bin/env python3
"""Seed DynamoDB with reports from a YAML dashboard config file.

Each entry under the ``reports`` key in the YAML becomes a separate report
record in DynamoDB.  The script is idempotent by default: if a report with
the same name already exists it is skipped.  Use ``--force`` to create
duplicates anyway.

Usage (inside the seizu container)::

    PYTHONPATH=/home/seizu/seizu pipenv run python scripts/seed_reports_from_yaml.py
    PYTHONPATH=/home/seizu/seizu pipenv run python scripts/seed_reports_from_yaml.py --config /path/to/other.yaml
    PYTHONPATH=/home/seizu/seizu pipenv run python scripts/seed_reports_from_yaml.py --force
    PYTHONPATH=/home/seizu/seizu pipenv run python scripts/seed_reports_from_yaml.py --dry-run

Or via the Makefile shortcut::

    make seed_reports
    make seed_reports ARGS="--force"
    make seed_reports ARGS="--dry-run"

Environment variables (all optional; defaults match docker-compose dev setup):

    DYNAMODB_TABLE_NAME      default: seizu-reports
    DYNAMODB_REGION          default: us-east-1
    DYNAMODB_ENDPOINT_URL    default: "" (use AWS default endpoint)
    DYNAMODB_CREATE_TABLE    default: false
    REPORTING_CONFIG_FILE    default: /reporting-dashboard.conf
    SNOWFLAKE_MACHINE_ID     default: 1
"""
import argparse
import sys

from reporting import settings
from reporting.schema import reporting_config
from reporting.services import report_store


SEED_USER = "seed-script"
SEED_COMMENT = "Imported from YAML dashboard config"


def _existing_names() -> set:
    """Return the set of report names already stored in DynamoDB."""
    try:
        reports = report_store.list_reports()
        return {r.name for r in reports}
    except Exception as exc:
        print(f"[warn] Could not fetch existing reports: {exc}", file=sys.stderr)
        return set()


def seed(config_file: str, force: bool, dry_run: bool) -> None:
    config = reporting_config.load_file(config_file)

    if not config.reports:
        print("No reports found in config file. Nothing to do.")
        return

    if settings.DYNAMODB_CREATE_TABLE and not dry_run:
        report_store.initialize()

    existing = set() if force else _existing_names()

    created = 0
    skipped = 0
    # Maps yaml key -> seeded report_id, used to resolve the dashboard pointer.
    seeded_ids: dict = {}

    for report_id_key, report in config.reports.items():
        if report.name in existing:
            print(
                f"[skip] '{report.name}' (name already exists; use --force to override)"  # noqa: E702
            )
            skipped += 1
            continue

        report_config_dict = report.model_dump()

        if dry_run:
            print(
                f"[dry-run] would create report '{report.name}' (key: {report_id_key})"
            )
            created += 1
            continue

        result = report_store.create_report(
            config=report_config_dict,
            created_by=SEED_USER,
            comment=SEED_COMMENT,
        )
        seeded_ids[report_id_key] = result.report_id
        print(
            f"[created] '{result.report_id}' name='{report.name}'"
            f" version={result.version} yaml_key='{report_id_key}'"
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

    print(
        f"\nDone. created={created} skipped={skipped}"
        + (" (dry-run, no writes performed)" if dry_run else "")
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed DynamoDB reports from a YAML dashboard config file."
    )
    parser.add_argument(
        "--config",
        default=settings.REPORTING_CONFIG_FILE,
        help=(
            "Path to the YAML dashboard config file "
            f"(default: {settings.REPORTING_CONFIG_FILE})"
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Create reports even if a report with the same name already exists.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be created without writing anything to DynamoDB.",
    )
    args = parser.parse_args()

    seed(config_file=args.config, force=args.force, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
