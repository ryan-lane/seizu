"""CLI commands for managing toolsets and tools."""
import json
import sys
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from seizu_cli import state
from seizu_cli.client import APIError

app = typer.Typer(help="Manage toolsets and tools.", no_args_is_help=True)
tools_app = typer.Typer(help="Manage tools within a toolset.", no_args_is_help=True)
app.add_typer(tools_app, name="tools")

console = Console()
err_console = Console(stderr=True)


def _die(exc: Exception) -> None:
    if isinstance(exc, APIError):
        err_console.print(f"[red]Error {exc.status_code}[/red]: {exc}")
    else:
        err_console.print(f"[red]Error[/red]: {exc}")
    sys.exit(1)


def _print_toolset_detail(data: Dict[str, Any], as_json: bool) -> None:
    if as_json:
        console.print_json(json.dumps(data))
        return
    console.print(f"[bold]ID[/bold]: {data['toolset_id']}")
    console.print(f"[bold]Name[/bold]: {data['name']}")
    console.print(f"[bold]Description[/bold]: {data.get('description', '')}")
    console.print(f"[bold]Enabled[/bold]: {data.get('enabled', True)}")
    console.print(
        f"[bold]Version[/bold]: {data.get('current_version', data.get('version'))}"
    )
    console.print(f"[bold]Created By[/bold]: {data['created_by']}")
    console.print(f"[bold]Updated By[/bold]: {data.get('updated_by', '')}")


def _print_tool_detail(data: Dict[str, Any], as_json: bool) -> None:
    if as_json:
        console.print_json(json.dumps(data))
        return
    console.print(f"[bold]ID[/bold]: {data['tool_id']}")
    console.print(f"[bold]Toolset ID[/bold]: {data['toolset_id']}")
    console.print(f"[bold]Name[/bold]: {data['name']}")
    console.print(f"[bold]Description[/bold]: {data.get('description', '')}")
    console.print(f"[bold]Enabled[/bold]: {data.get('enabled', True)}")
    console.print(
        f"[bold]Version[/bold]: {data.get('current_version', data.get('version'))}"
    )
    console.print(f"[bold]Created By[/bold]: {data['created_by']}")
    console.print(f"[bold]Updated By[/bold]: {data.get('updated_by', '')}")
    if data.get("parameters"):
        console.print(f"[bold]Parameters[/bold]: {json.dumps(data['parameters'])}")
    console.print(f"[bold]Cypher[/bold]\n{data['cypher']}")


# ---------------------------------------------------------------------------
# Toolset commands
# ---------------------------------------------------------------------------


@app.command("list")
def list_toolsets(
    output: str = typer.Option(
        "table", "--output", "-o", help="Output format: table or json."
    ),
) -> None:
    """List all toolsets."""
    try:
        data = state.get_client().get("/api/v1/toolsets")
    except Exception as exc:
        _die(exc)
        return

    if output == "json":
        console.print_json(json.dumps(data))
        return

    items = data.get("toolsets", [])
    if not items:
        console.print("[dim]No toolsets found.[/dim]")
        return

    table = Table(show_header=True, header_style="bold")
    table.add_column("ID")
    table.add_column("Name")
    table.add_column("Description")
    table.add_column("Enabled")
    table.add_column("Version", justify="right")
    table.add_column("Updated At")

    for ts in items:
        table.add_row(
            ts["toolset_id"],
            ts["name"],
            ts.get("description", ""),
            "yes" if ts.get("enabled", True) else "no",
            str(ts.get("current_version", "")),
            ts.get("updated_at", ""),
        )

    console.print(table)


@app.command("get")
def get_toolset(
    toolset_id: str = typer.Argument(help="Toolset ID."),
    output: str = typer.Option(
        "table", "--output", "-o", help="Output format: table or json."
    ),
) -> None:
    """Get a toolset by ID."""
    try:
        data = state.get_client().get(f"/api/v1/toolsets/{toolset_id}")
    except Exception as exc:
        _die(exc)
        return
    _print_toolset_detail(data, as_json=(output == "json"))


@app.command("create")
def create_toolset(
    name: str = typer.Argument(help="Toolset name."),
    description: str = typer.Option("", "--description", "-d", help="Description."),
    disabled: bool = typer.Option(False, "--disabled", help="Create as disabled."),
) -> None:
    """Create a new toolset."""
    try:
        data = state.get_client().post(
            "/api/v1/toolsets",
            json={"name": name, "description": description, "enabled": not disabled},
        )
    except Exception as exc:
        _die(exc)
        return
    console.print(
        f"[green]Created[/green]: {data['toolset_id']}  name={data['name']!r}"
    )


@app.command("update")
def update_toolset(
    toolset_id: str = typer.Argument(help="Toolset ID."),
    name: str = typer.Option(..., "--name", "-n", help="New name."),
    description: str = typer.Option("", "--description", "-d", help="Description."),
    enabled: bool = typer.Option(
        True, "--enabled/--disabled", help="Enable or disable."
    ),
    comment: Optional[str] = typer.Option(
        None, "--comment", "-c", help="Version comment."
    ),
) -> None:
    """Update a toolset (creates a new version)."""
    try:
        data = state.get_client().put(
            f"/api/v1/toolsets/{toolset_id}",
            json={
                "name": name,
                "description": description,
                "enabled": enabled,
                "comment": comment,
            },
        )
    except Exception as exc:
        _die(exc)
        return
    _print_toolset_detail(data, as_json=False)


@app.command("delete")
def delete_toolset(
    toolset_id: str = typer.Argument(help="Toolset ID."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt."),
) -> None:
    """Delete a toolset and all its tools."""
    if not yes:
        typer.confirm(f"Delete toolset {toolset_id!r} and all its tools?", abort=True)
    try:
        state.get_client().delete(f"/api/v1/toolsets/{toolset_id}")
    except Exception as exc:
        _die(exc)
        return
    console.print(f"[red]Deleted[/red]: {toolset_id}")


@app.command("versions")
def list_toolset_versions(
    toolset_id: str = typer.Argument(help="Toolset ID."),
    output: str = typer.Option(
        "table", "--output", "-o", help="Output format: table or json."
    ),
) -> None:
    """List all versions of a toolset."""
    try:
        data = state.get_client().get(f"/api/v1/toolsets/{toolset_id}/versions")
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
def get_toolset_version(
    toolset_id: str = typer.Argument(help="Toolset ID."),
    version: int = typer.Argument(help="Version number."),
    output: str = typer.Option(
        "table", "--output", "-o", help="Output format: table or json."
    ),
) -> None:
    """Get a specific version of a toolset."""
    try:
        data = state.get_client().get(
            f"/api/v1/toolsets/{toolset_id}/versions/{version}"
        )
    except Exception as exc:
        _die(exc)
        return
    _print_toolset_detail(data, as_json=(output == "json"))


# ---------------------------------------------------------------------------
# Tool commands (nested under toolsets tools)
# ---------------------------------------------------------------------------


@tools_app.command("list")
def list_tools(
    toolset_id: str = typer.Argument(help="Toolset ID."),
    output: str = typer.Option(
        "table", "--output", "-o", help="Output format: table or json."
    ),
) -> None:
    """List all tools in a toolset."""
    try:
        data = state.get_client().get(f"/api/v1/toolsets/{toolset_id}/tools")
    except Exception as exc:
        _die(exc)
        return

    if output == "json":
        console.print_json(json.dumps(data))
        return

    items = data.get("tools", [])
    if not items:
        console.print("[dim]No tools found.[/dim]")
        return

    table = Table(show_header=True, header_style="bold")
    table.add_column("ID")
    table.add_column("Name")
    table.add_column("Description")
    table.add_column("Enabled")
    table.add_column("Version", justify="right")
    table.add_column("Updated At")

    for t in items:
        table.add_row(
            t["tool_id"],
            t["name"],
            t.get("description", ""),
            "yes" if t.get("enabled", True) else "no",
            str(t.get("current_version", "")),
            t.get("updated_at", ""),
        )

    console.print(table)


@tools_app.command("get")
def get_tool(
    toolset_id: str = typer.Argument(help="Toolset ID."),
    tool_id: str = typer.Argument(help="Tool ID."),
    output: str = typer.Option(
        "table", "--output", "-o", help="Output format: table or json."
    ),
) -> None:
    """Get a tool by ID."""
    try:
        data = state.get_client().get(f"/api/v1/toolsets/{toolset_id}/tools/{tool_id}")
    except Exception as exc:
        _die(exc)
        return
    _print_tool_detail(data, as_json=(output == "json"))


@tools_app.command("create")
def create_tool(
    toolset_id: str = typer.Argument(help="Toolset ID."),
    name: str = typer.Option(..., "--name", "-n", help="Tool name."),
    cypher: str = typer.Option(..., "--cypher", help="Cypher query."),
    description: str = typer.Option("", "--description", "-d", help="Description."),
    parameters: Optional[str] = typer.Option(
        None,
        "--parameters",
        help="Parameters as a JSON array of ToolParamDef objects.",
    ),
    disabled: bool = typer.Option(False, "--disabled", help="Create as disabled."),
) -> None:
    """Create a new tool within a toolset."""
    params: List[Dict[str, Any]] = []
    if parameters:
        try:
            params = json.loads(parameters)
        except json.JSONDecodeError as exc:
            err_console.print(
                f"[red]Error[/red]: --parameters is not valid JSON: {exc}"
            )
            sys.exit(1)
    try:
        data = state.get_client().post(
            f"/api/v1/toolsets/{toolset_id}/tools",
            json={
                "name": name,
                "description": description,
                "cypher": cypher,
                "parameters": params,
                "enabled": not disabled,
            },
        )
    except Exception as exc:
        _die(exc)
        return
    console.print(f"[green]Created[/green]: {data['tool_id']}  name={data['name']!r}")


@tools_app.command("update")
def update_tool(
    toolset_id: str = typer.Argument(help="Toolset ID."),
    tool_id: str = typer.Argument(help="Tool ID."),
    name: str = typer.Option(..., "--name", "-n", help="New name."),
    cypher: str = typer.Option(..., "--cypher", help="Cypher query."),
    description: str = typer.Option("", "--description", "-d", help="Description."),
    parameters: Optional[str] = typer.Option(
        None,
        "--parameters",
        help="Parameters as a JSON array of ToolParamDef objects.",
    ),
    enabled: bool = typer.Option(
        True, "--enabled/--disabled", help="Enable or disable."
    ),
    comment: Optional[str] = typer.Option(
        None, "--comment", "-c", help="Version comment."
    ),
) -> None:
    """Update a tool (creates a new version)."""
    params: List[Dict[str, Any]] = []
    if parameters:
        try:
            params = json.loads(parameters)
        except json.JSONDecodeError as exc:
            err_console.print(
                f"[red]Error[/red]: --parameters is not valid JSON: {exc}"
            )
            sys.exit(1)
    try:
        data = state.get_client().put(
            f"/api/v1/toolsets/{toolset_id}/tools/{tool_id}",
            json={
                "name": name,
                "description": description,
                "cypher": cypher,
                "parameters": params,
                "enabled": enabled,
                "comment": comment,
            },
        )
    except Exception as exc:
        _die(exc)
        return
    _print_tool_detail(data, as_json=False)


@tools_app.command("delete")
def delete_tool(
    toolset_id: str = typer.Argument(help="Toolset ID."),
    tool_id: str = typer.Argument(help="Tool ID."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt."),
) -> None:
    """Delete a tool."""
    if not yes:
        typer.confirm(f"Delete tool {tool_id!r}?", abort=True)
    try:
        state.get_client().delete(f"/api/v1/toolsets/{toolset_id}/tools/{tool_id}")
    except Exception as exc:
        _die(exc)
        return
    console.print(f"[red]Deleted[/red]: {tool_id}")


@tools_app.command("call")
def call_tool(
    toolset_id: str = typer.Argument(help="Toolset ID."),
    tool_id: str = typer.Argument(help="Tool ID."),
    arg: List[str] = typer.Option(
        [],
        "--arg",
        help=(
            "Argument as KEY=VALUE where VALUE is a JSON literal "
            "(e.g. --arg limit=10 --arg name='\"foo\"'). "
            "Ignored if --args-json is provided."
        ),
    ),
    args_json: Optional[str] = typer.Option(
        None,
        "--args-json",
        help="All arguments as a JSON object (overrides --arg).",
    ),
    output: str = typer.Option(
        "table", "--output", "-o", help="Output format: table or json."
    ),
) -> None:
    """Execute a tool's Cypher query with the provided arguments."""
    arguments: Dict[str, Any] = {}

    if args_json is not None:
        try:
            arguments = json.loads(args_json)
        except json.JSONDecodeError as exc:
            err_console.print(f"[red]Error[/red]: --args-json is not valid JSON: {exc}")
            sys.exit(1)
    elif arg:
        for pair in arg:
            if "=" not in pair:
                err_console.print(f"[red]Error[/red]: --arg {pair!r} must be KEY=VALUE")
                sys.exit(1)
            key, _, raw_value = pair.partition("=")
            try:
                arguments[key] = json.loads(raw_value)
            except json.JSONDecodeError:
                # Treat as plain string if not valid JSON
                arguments[key] = raw_value

    try:
        data = state.get_client().post(
            f"/api/v1/toolsets/{toolset_id}/tools/{tool_id}/call",
            json={"arguments": arguments},
        )
    except Exception as exc:
        _die(exc)
        return

    if output == "json":
        console.print_json(json.dumps(data))
        return

    results = data.get("results", [])
    if not results:
        console.print("[dim]No results.[/dim]")
        return

    # Build table from first result's keys
    columns = list(results[0].keys()) if results else []
    table = Table(show_header=True, header_style="bold")
    for col in columns:
        table.add_column(col)

    for row in results:
        table.add_row(*[str(row.get(c, "")) for c in columns])

    console.print(table)


@tools_app.command("versions")
def list_tool_versions(
    toolset_id: str = typer.Argument(help="Toolset ID."),
    tool_id: str = typer.Argument(help="Tool ID."),
    output: str = typer.Option(
        "table", "--output", "-o", help="Output format: table or json."
    ),
) -> None:
    """List all versions of a tool."""
    try:
        data = state.get_client().get(
            f"/api/v1/toolsets/{toolset_id}/tools/{tool_id}/versions"
        )
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


@tools_app.command("version-get")
def get_tool_version(
    toolset_id: str = typer.Argument(help="Toolset ID."),
    tool_id: str = typer.Argument(help="Tool ID."),
    version: int = typer.Argument(help="Version number."),
    output: str = typer.Option(
        "table", "--output", "-o", help="Output format: table or json."
    ),
) -> None:
    """Get a specific version of a tool."""
    try:
        data = state.get_client().get(
            f"/api/v1/toolsets/{toolset_id}/tools/{tool_id}/versions/{version}"
        )
    except Exception as exc:
        _die(exc)
        return
    _print_tool_detail(data, as_json=(output == "json"))
