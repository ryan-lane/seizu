"""CLI commands for managing skillsets and skills."""

import json
import sys
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from seizu_cli import state
from seizu_cli.client import APIError

app = typer.Typer(help="Manage skillsets and skills.", no_args_is_help=True)
skills_app = typer.Typer(help="Manage skills within a skillset.", no_args_is_help=True)
app.add_typer(skills_app, name="skills")

console = Console()
err_console = Console(stderr=True)


def _die(exc: Exception) -> None:
    if isinstance(exc, APIError):
        err_console.print(f"[red]Error {exc.status_code}[/red]: {exc}")
    else:
        err_console.print(f"[red]Error[/red]: {exc}")
    sys.exit(1)


def _json_arg(value: str | None, label: str) -> Any:
    if value is None:
        return [] if label in ("parameters", "triggers", "tools-required") else {}
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        err_console.print(f"[red]Error[/red]: --{label} is not valid JSON: {exc}")
        sys.exit(1)


def _print_table(items: list[dict[str, Any]], id_key: str) -> None:
    table = Table(show_header=True, header_style="bold")
    table.add_column("ID")
    table.add_column("Name")
    table.add_column("Description")
    table.add_column("Enabled")
    table.add_column("Version", justify="right")
    table.add_column("Updated At")
    for item in items:
        table.add_row(
            item[id_key],
            item["name"],
            item.get("description", ""),
            "yes" if item.get("enabled", True) else "no",
            str(item.get("current_version", "")),
            item.get("updated_at", ""),
        )
    console.print(table)


def _print_detail(data: dict[str, Any], id_key: str, as_json: bool) -> None:
    if as_json:
        console.print_json(json.dumps(data))
        return
    console.print(f"[bold]ID[/bold]: {data[id_key]}")
    if "skillset_id" in data and id_key == "skill_id":
        console.print(f"[bold]Skillset ID[/bold]: {data['skillset_id']}")
    console.print(f"[bold]Name[/bold]: {data['name']}")
    console.print(f"[bold]Description[/bold]: {data.get('description', '')}")
    console.print(f"[bold]Enabled[/bold]: {data.get('enabled', True)}")
    console.print(f"[bold]Version[/bold]: {data.get('current_version', data.get('version'))}")
    console.print(f"[bold]Created By[/bold]: {data['created_by']}")
    console.print(f"[bold]Updated By[/bold]: {data.get('updated_by', '')}")
    if data.get("parameters"):
        console.print(f"[bold]Parameters[/bold]: {json.dumps(data['parameters'])}")
    if data.get("triggers"):
        console.print(f"[bold]Triggers[/bold]: {json.dumps(data['triggers'])}")
    if data.get("tools_required"):
        console.print(f"[bold]Tools Required[/bold]: {json.dumps(data['tools_required'])}")
    if data.get("template"):
        console.print(f"[bold]Template[/bold]\n{data['template']}")


@app.command("list")
def list_skillsets(output: str = typer.Option("table", "--output", "-o", help="Output format: table or json.")) -> None:
    try:
        data = state.get_client().get("/api/v1/skillsets")
    except Exception as exc:
        _die(exc)
        return
    if output == "json":
        console.print_json(json.dumps(data))
        return
    _print_table(data.get("skillsets", []), "skillset_id")


@app.command("get")
def get_skillset(
    skillset_id: str = typer.Argument(help="Skillset ID."),
    output: str = typer.Option("table", "--output", "-o", help="Output format: table or json."),
) -> None:
    try:
        data = state.get_client().get(f"/api/v1/skillsets/{skillset_id}")
    except Exception as exc:
        _die(exc)
        return
    _print_detail(data, "skillset_id", output == "json")


@app.command("create")
def create_skillset(
    skillset_id: str = typer.Argument(help="Immutable lower_snake_case skillset ID."),
    name: str = typer.Argument(help="Skillset name."),
    description: str = typer.Option("", "--description", "-d", help="Description."),
    disabled: bool = typer.Option(False, "--disabled", help="Create as disabled."),
) -> None:
    try:
        data = state.get_client().post(
            "/api/v1/skillsets",
            json={"skillset_id": skillset_id, "name": name, "description": description, "enabled": not disabled},
        )
    except Exception as exc:
        _die(exc)
        return
    console.print(f"[green]Created[/green]: {data['skillset_id']}  name={data['name']!r}")


@app.command("update")
def update_skillset(
    skillset_id: str = typer.Argument(help="Skillset ID."),
    name: str = typer.Option(..., "--name", "-n", help="New name."),
    description: str = typer.Option("", "--description", "-d", help="Description."),
    enabled: bool = typer.Option(True, "--enabled/--disabled", help="Enable or disable."),
    comment: str | None = typer.Option(None, "--comment", "-c", help="Version comment."),
) -> None:
    try:
        data = state.get_client().put(
            f"/api/v1/skillsets/{skillset_id}",
            json={"name": name, "description": description, "enabled": enabled, "comment": comment},
        )
    except Exception as exc:
        _die(exc)
        return
    _print_detail(data, "skillset_id", False)


@app.command("delete")
def delete_skillset(
    skillset_id: str = typer.Argument(help="Skillset ID."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt."),
) -> None:
    if not yes:
        typer.confirm(f"Delete skillset {skillset_id!r} and all its skills?", abort=True)
    try:
        state.get_client().delete(f"/api/v1/skillsets/{skillset_id}")
    except Exception as exc:
        _die(exc)
        return
    console.print(f"[red]Deleted[/red]: {skillset_id}")


@app.command("versions")
def list_skillset_versions(
    skillset_id: str = typer.Argument(help="Skillset ID."),
    output: str = typer.Option("table", "--output", "-o", help="Output format: table or json."),
) -> None:
    try:
        data = state.get_client().get(f"/api/v1/skillsets/{skillset_id}/versions")
    except Exception as exc:
        _die(exc)
        return
    if output == "json":
        console.print_json(json.dumps(data))
        return
    _print_versions(data.get("versions", []))


@app.command("version-get")
def get_skillset_version(
    skillset_id: str = typer.Argument(help="Skillset ID."),
    version: int = typer.Argument(help="Version number."),
    output: str = typer.Option("table", "--output", "-o", help="Output format: table or json."),
) -> None:
    try:
        data = state.get_client().get(f"/api/v1/skillsets/{skillset_id}/versions/{version}")
    except Exception as exc:
        _die(exc)
        return
    _print_detail(data, "skillset_id", output == "json")


def _print_versions(versions: list[dict[str, Any]]) -> None:
    table = Table(show_header=True, header_style="bold")
    table.add_column("Version", justify="right")
    table.add_column("Created By")
    table.add_column("Created At")
    table.add_column("Comment")
    for v in versions:
        table.add_row(str(v["version"]), v["created_by"], v["created_at"], v.get("comment") or "")
    console.print(table)


@skills_app.command("list")
def list_skills(
    skillset_id: str = typer.Argument(help="Skillset ID."),
    output: str = typer.Option("table", "--output", "-o", help="Output format: table or json."),
) -> None:
    try:
        data = state.get_client().get(f"/api/v1/skillsets/{skillset_id}/skills")
    except Exception as exc:
        _die(exc)
        return
    if output == "json":
        console.print_json(json.dumps(data))
        return
    _print_table(data.get("skills", []), "skill_id")


@skills_app.command("get")
def get_skill(
    skillset_id: str = typer.Argument(help="Skillset ID."),
    skill_id: str = typer.Argument(help="Skill ID."),
    output: str = typer.Option("table", "--output", "-o", help="Output format: table or json."),
) -> None:
    try:
        data = state.get_client().get(f"/api/v1/skillsets/{skillset_id}/skills/{skill_id}")
    except Exception as exc:
        _die(exc)
        return
    _print_detail(data, "skill_id", output == "json")


@skills_app.command("create")
def create_skill(
    skillset_id: str = typer.Argument(help="Skillset ID."),
    skill_id: str = typer.Argument(help="Immutable lower_snake_case skill ID."),
    name: str = typer.Option(..., "--name", "-n", help="Skill name."),
    template: str = typer.Option(..., "--template", help="Prompt template."),
    description: str = typer.Option("", "--description", "-d", help="Description."),
    parameters: str | None = typer.Option(None, "--parameters", help="Parameters as a JSON array."),
    triggers: str | None = typer.Option(None, "--triggers", help="Triggers as a JSON array of strings."),
    tools_required: str | None = typer.Option(
        None,
        "--tools-required",
        help="Required MCP tool names as a JSON array of strings.",
    ),
    disabled: bool = typer.Option(False, "--disabled", help="Create as disabled."),
) -> None:
    try:
        data = state.get_client().post(
            f"/api/v1/skillsets/{skillset_id}/skills",
            json={
                "skill_id": skill_id,
                "name": name,
                "description": description,
                "template": template,
                "parameters": _json_arg(parameters, "parameters"),
                "triggers": _json_arg(triggers, "triggers"),
                "tools_required": _json_arg(tools_required, "tools-required"),
                "enabled": not disabled,
            },
        )
    except Exception as exc:
        _die(exc)
        return
    console.print(f"[green]Created[/green]: {data['skill_id']}  name={data['name']!r}")


@skills_app.command("update")
def update_skill(
    skillset_id: str = typer.Argument(help="Skillset ID."),
    skill_id: str = typer.Argument(help="Skill ID."),
    name: str = typer.Option(..., "--name", "-n", help="New name."),
    template: str = typer.Option(..., "--template", help="Prompt template."),
    description: str = typer.Option("", "--description", "-d", help="Description."),
    parameters: str | None = typer.Option(None, "--parameters", help="Parameters as a JSON array."),
    triggers: str | None = typer.Option(None, "--triggers", help="Triggers as a JSON array of strings."),
    tools_required: str | None = typer.Option(
        None,
        "--tools-required",
        help="Required MCP tool names as a JSON array of strings.",
    ),
    enabled: bool = typer.Option(True, "--enabled/--disabled", help="Enable or disable."),
    comment: str | None = typer.Option(None, "--comment", "-c", help="Version comment."),
) -> None:
    try:
        data = state.get_client().put(
            f"/api/v1/skillsets/{skillset_id}/skills/{skill_id}",
            json={
                "name": name,
                "description": description,
                "template": template,
                "parameters": _json_arg(parameters, "parameters"),
                "triggers": _json_arg(triggers, "triggers"),
                "tools_required": _json_arg(tools_required, "tools-required"),
                "enabled": enabled,
                "comment": comment,
            },
        )
    except Exception as exc:
        _die(exc)
        return
    _print_detail(data, "skill_id", False)


@skills_app.command("delete")
def delete_skill(
    skillset_id: str = typer.Argument(help="Skillset ID."),
    skill_id: str = typer.Argument(help="Skill ID."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt."),
) -> None:
    if not yes:
        typer.confirm(f"Delete skill {skill_id!r}?", abort=True)
    try:
        state.get_client().delete(f"/api/v1/skillsets/{skillset_id}/skills/{skill_id}")
    except Exception as exc:
        _die(exc)
        return
    console.print(f"[red]Deleted[/red]: {skill_id}")


@skills_app.command("render")
def render_skill(
    skillset_id: str = typer.Argument(help="Skillset ID."),
    skill_id: str = typer.Argument(help="Skill ID."),
    args_json: str | None = typer.Option(None, "--args-json", help="Arguments as a JSON object."),
    output: str = typer.Option("text", "--output", "-o", help="Output format: text or json."),
) -> None:
    try:
        data = state.get_client().post(
            f"/api/v1/skillsets/{skillset_id}/skills/{skill_id}/render",
            json={"arguments": _json_arg(args_json, "args-json")},
        )
    except Exception as exc:
        _die(exc)
        return
    if output == "json":
        console.print_json(json.dumps(data))
        return
    console.print(data.get("text", ""))


@skills_app.command("versions")
def list_skill_versions(
    skillset_id: str = typer.Argument(help="Skillset ID."),
    skill_id: str = typer.Argument(help="Skill ID."),
    output: str = typer.Option("table", "--output", "-o", help="Output format: table or json."),
) -> None:
    try:
        data = state.get_client().get(f"/api/v1/skillsets/{skillset_id}/skills/{skill_id}/versions")
    except Exception as exc:
        _die(exc)
        return
    if output == "json":
        console.print_json(json.dumps(data))
        return
    _print_versions(data.get("versions", []))


@skills_app.command("version-get")
def get_skill_version(
    skillset_id: str = typer.Argument(help="Skillset ID."),
    skill_id: str = typer.Argument(help="Skill ID."),
    version: int = typer.Argument(help="Version number."),
    output: str = typer.Option("table", "--output", "-o", help="Output format: table or json."),
) -> None:
    try:
        data = state.get_client().get(f"/api/v1/skillsets/{skillset_id}/skills/{skill_id}/versions/{version}")
    except Exception as exc:
        _die(exc)
        return
    _print_detail(data, "skill_id", output == "json")
