"""CLI commands for managing reports."""

import json
import sys
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from seizu_cli import state
from seizu_cli.client import APIError

app = typer.Typer(help="Manage reports.", no_args_is_help=True)
console = Console()
err_console = Console(stderr=True)


def _die(exc: Exception) -> None:
    if isinstance(exc, APIError):
        err_console.print(f"[red]Error {exc.status_code}[/red]: {exc}")
    else:
        err_console.print(f"[red]Error[/red]: {exc}")
    sys.exit(1)


def _print_report_detail(data: dict[str, Any], as_json: bool) -> None:
    if as_json:
        sanitized = dict(data)
        sanitized.pop("query_capabilities", None)
        console.print_json(json.dumps(sanitized))
        return
    console.print(f"[bold]ID[/bold]: {data['report_id']}")
    console.print(f"[bold]Name[/bold]: {data['name']}")
    console.print(f"[bold]Version[/bold]: {data['version']}")
    console.print(f"[bold]Created By[/bold]: {data['created_by']}")
    console.print(f"[bold]Created At[/bold]: {data['created_at']}")
    if data.get("comment"):
        console.print(f"[bold]Comment[/bold]: {data['comment']}")


@app.command("list")
def list_reports(
    output: str = typer.Option("table", "--output", "-o", help="Output format: table or json."),
) -> None:
    """List all reports."""
    try:
        data = state.get_client().get("/api/v1/reports")
    except Exception as exc:
        _die(exc)
        return

    if output == "json":
        console.print_json(json.dumps(data))
        return

    reports = data.get("reports", [])
    if not reports:
        console.print("[dim]No reports found.[/dim]")
        return

    table = Table(show_header=True, header_style="bold")
    table.add_column("ID")
    table.add_column("Name")
    table.add_column("Version", justify="right")
    table.add_column("Updated At")

    for r in reports:
        table.add_row(r["report_id"], r["name"], str(r["current_version"]), r["updated_at"])

    console.print(table)


@app.command("get")
def get_report(
    report_id: str = typer.Argument(help="Report ID."),
    output: str = typer.Option("table", "--output", "-o", help="Output format: table or json."),
) -> None:
    """Get the latest version of a report."""
    try:
        data = state.get_client().get(f"/api/v1/reports/{report_id}")
    except Exception as exc:
        _die(exc)
        return
    _print_report_detail(data, as_json=(output == "json"))


@app.command("create")
def create_report(
    name: str = typer.Argument(help="Report name."),
) -> None:
    """Create a new empty report."""
    try:
        data = state.get_client().post("/api/v1/reports", json={"name": name})
    except Exception as exc:
        _die(exc)
        return
    console.print(f"[green]Created[/green]: {data['report_id']}  name={data['name']!r}")


@app.command("clone")
def clone_report(
    report_id: str = typer.Argument(help="Source report ID."),
    name: str = typer.Argument(help="Name for the cloned report."),
) -> None:
    """Clone a report into a new report."""
    try:
        data = state.get_client().post(f"/api/v1/reports/{report_id}/clone", json={"name": name})
    except Exception as exc:
        _die(exc)
        return
    console.print(f"[green]Cloned[/green]: {data['report_id']}  name={data['name']!r}  source={report_id!r}")


@app.command("delete")
def delete_report(
    report_id: str = typer.Argument(help="Report ID."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt."),
) -> None:
    """Delete a report and all its versions."""
    if not yes:
        typer.confirm(f"Delete report {report_id!r} and all its versions?", abort=True)
    try:
        state.get_client().delete(f"/api/v1/reports/{report_id}")
    except Exception as exc:
        _die(exc)
        return
    console.print(f"[red]Deleted[/red]: {report_id}")


@app.command("set-dashboard")
def set_dashboard(
    report_id: str = typer.Argument(help="Report ID to set as the default dashboard."),
) -> None:
    """Set a report as the default dashboard."""
    try:
        state.get_client().put(f"/api/v1/reports/{report_id}/dashboard")
    except Exception as exc:
        _die(exc)
        return
    console.print(f"[green]Dashboard set to[/green]: {report_id}")


@app.command("versions")
def list_versions(
    report_id: str = typer.Argument(help="Report ID."),
    output: str = typer.Option("table", "--output", "-o", help="Output format: table or json."),
) -> None:
    """List all versions of a report."""
    try:
        data = state.get_client().get(f"/api/v1/reports/{report_id}/versions")
    except Exception as exc:
        _die(exc)
        return

    if output == "json":
        console.print_json(json.dumps(data))
        return

    versions = data.get("versions", [])
    table = Table(show_header=True, header_style="bold")
    table.add_column("Version", justify="right")
    table.add_column("Created By")
    table.add_column("Created At")
    table.add_column("Comment")

    for v in versions:
        table.add_row(
            str(v["version"]),
            v["created_by"],
            v["created_at"],
            v.get("comment") or "",
        )
    console.print(table)


@app.command("version-get")
def get_version(
    report_id: str = typer.Argument(help="Report ID."),
    version: int = typer.Argument(help="Version number."),
    output: str = typer.Option("table", "--output", "-o", help="Output format: table or json."),
) -> None:
    """Get a specific version of a report."""
    try:
        data = state.get_client().get(f"/api/v1/reports/{report_id}/versions/{version}")
    except Exception as exc:
        _die(exc)
        return
    _print_report_detail(data, as_json=(output == "json"))
