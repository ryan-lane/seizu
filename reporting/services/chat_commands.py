"""Slash command parsing for the chat assistant."""

import json
import shlex
from typing import Any, Literal

from pydantic import BaseModel, Field


class SlashCommand(BaseModel):
    command: Literal["tools", "tool", "skills", "skill"]
    name: str | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)


class SlashCommandError(ValueError):
    pass


def parse_slash_command(text: str) -> SlashCommand | None:
    """Parse a chat slash command, returning None for ordinary messages.

    Commands:
    - /tools
    - /skills
    - /tool <name> [{...json args...}]
    - /skill <name> [{...json args...}]
    """
    stripped = text.strip()
    if not stripped.startswith("/"):
        return None

    command_token, name, json_text = _split_command(stripped)
    command = command_token.removeprefix("/")
    if command not in {"tools", "tool", "skills", "skill"}:
        return None

    if command in {"tools", "skills"}:
        if name or json_text:
            raise SlashCommandError(f"`/{command}` does not accept arguments.")
        return SlashCommand(command=command)

    if not name:
        raise SlashCommandError(f"Expected `/{command} <name> {{...json args...}}`.")
    return SlashCommand(command=command, name=name, arguments=_parse_arguments(json_text))


def _split_command(text: str) -> tuple[str, str | None, str]:
    try:
        tokens = shlex.split(text, posix=True)
    except ValueError as exc:
        raise SlashCommandError(str(exc)) from exc

    if not tokens:
        return "", None, ""
    if len(tokens) <= 2:
        return tokens[0], tokens[1] if len(tokens) == 2 else None, ""

    # Prefer shell-style parsing when the JSON object was quoted as one token.
    if len(tokens) == 3:
        return tokens[0], tokens[1], tokens[2]

    # Preserve support for the friendlier unquoted form:
    # /tool name {"limit": 3}
    parts = text.split(maxsplit=2)
    return parts[0], parts[1] if len(parts) > 1 else None, parts[2] if len(parts) > 2 else ""


def _parse_arguments(json_text: str) -> dict[str, Any]:
    if not json_text:
        return {}
    try:
        parsed = json.loads(json_text)
    except json.JSONDecodeError as exc:
        raise SlashCommandError("Arguments must be a JSON object.") from exc
    if not isinstance(parsed, dict):
        raise SlashCommandError("Arguments must be a JSON object.")
    return parsed
