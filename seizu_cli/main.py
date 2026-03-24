"""Seizu CLI entry point."""
from pathlib import Path
from typing import Optional

import typer

from seizu_cli import auth
from seizu_cli import state
from seizu_cli.commands import auth as auth_commands
from seizu_cli.commands import reports
from seizu_cli.commands import scheduled_queries
from seizu_cli.commands import seed

app = typer.Typer(
    help="Seizu CLI — manage reports and scheduled queries via the Seizu API.",
    no_args_is_help=True,
)
app.add_typer(reports.app, name="reports")
app.add_typer(scheduled_queries.app, name="scheduled-queries")
app.add_typer(auth_commands.app, name="auth")


@app.callback()
def main(
    api_url: str = typer.Option(
        "http://localhost:8080",
        envvar="SEIZU_API_URL",
        help="Seizu API base URL.",
        show_default=True,
    ),
    token: Optional[str] = typer.Option(
        None,
        envvar="SEIZU_TOKEN",
        help=(
            "Bearer token for API authentication. "
            "If omitted, a stored token from 'seizu login' is used."
        ),
    ),
    credentials_file: Optional[Path] = typer.Option(
        None,
        envvar="SEIZU_CREDENTIALS_FILE",
        help=(
            "Path to a JSON credentials file. "
            "Forces file-based token storage even if an OS keyring is available."
        ),
    ),
) -> None:
    """Seizu CLI — manage reports and scheduled queries via the Seizu API.

    Authentication is handled via the Device Authorization Grant flow.
    Run 'seizu login' once; credentials are stored in
    ~/.config/seizu/credentials.json and loaded automatically on every
    subsequent command.

    \b
    Quick start:
        seizu login                # authenticate (opens browser URL)
        seizu reports list         # list reports
        seizu scheduled-queries list

    \b
    To use a different deployment:
        seizu --api-url https://seizu.example.com login
        seizu --api-url https://seizu.example.com reports list

    \b
    To generate client libraries in other languages from the OpenAPI spec:
        make generate_openapi           # exports schema/openapi.json
        make generate_client LANG=go    # generates a Go client
        make generate_client LANG=typescript-fetch
        make generate_client LANG=java

    See https://openapi-generator.tech/docs/generators for all supported languages.
    """
    state.api_url = api_url
    state.credentials_file = credentials_file

    if token:
        # Explicit --token / SEIZU_TOKEN takes precedence over stored credentials.
        state.token = token
    else:
        # Fall back to stored credentials for this API URL.
        state.token = auth.load_token(api_url, credentials_file)

    state.reset_client()


@app.command("login")
def login_cmd() -> None:
    """Authenticate via the Device Authorization Grant (RFC 8628).

    Fetches the OIDC configuration from the API, then starts a Device
    Authorization flow.  A URL and short code are displayed; open the URL
    in your browser, enter the code, and the CLI will receive an access
    token automatically.

    The token is stored in the OS-native keyring and loaded automatically on
    subsequent commands. Pass --credentials-file PATH to store in a plain JSON
    file instead.

    \b
    Example:
        seizu login
        seizu --api-url https://seizu.example.com login
        seizu --credentials-file ~/seizu-creds.json login
    """
    auth_commands.login()


@app.command("logout")
def logout_cmd() -> None:
    """Remove stored credentials for the current API URL."""
    auth_commands.logout()


@app.command("whoami")
def whoami_cmd() -> None:
    """Show the currently authenticated user."""
    auth_commands.whoami()


@app.command("seed")
def seed_cmd(
    config: str = typer.Option(
        ".config/dev/seizu/reporting-dashboard.yaml",
        envvar="REPORTING_CONFIG_FILE",
        help="Path to the YAML dashboard config file.",
        show_default=True,
    ),
    force: bool = typer.Option(
        False,
        help="Update existing records even if their content is unchanged.",
    ),
    dry_run: bool = typer.Option(
        False,
        help="Preview what would be created or updated without writing anything.",
    ),
) -> None:
    """Seed reports and scheduled queries from a YAML config file via the API."""
    seed.seed_cmd(config=config, force=force, dry_run=dry_run)


@app.command("export")
def export_cmd(
    config: str = typer.Option(
        ".config/dev/seizu/reporting-dashboard.yaml",
        envvar="REPORTING_CONFIG_FILE",
        help="Path to the YAML dashboard config file.",
        show_default=True,
    ),
    dry_run: bool = typer.Option(
        False,
        help="Print the resulting YAML without overwriting the config file.",
    ),
) -> None:
    """Export the latest version of every report from the API back into a YAML config file."""
    seed.export_cmd(config=config, dry_run=dry_run)
