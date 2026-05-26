import pytest

from reporting.services.chat_commands import SlashCommandError, parse_slash_command


def test_parse_returns_none_for_plain_text():
    assert parse_slash_command("show me tools") is None
    assert parse_slash_command("/toolsmith") is None


def test_parse_list_commands():
    assert parse_slash_command("/tools").command == "tools"
    assert parse_slash_command("  /skills  ").command == "skills"


def test_parse_named_json_command_with_unquoted_json():
    command = parse_slash_command('/tool security__lookup {"limit": 3}')

    assert command is not None
    assert command.command == "tool"
    assert command.name == "security__lookup"
    assert command.arguments == {"limit": 3}


def test_parse_named_json_command_with_quoted_json():
    command = parse_slash_command('/skill security__summarize \'{"topic": "alerts"}\'')

    assert command is not None
    assert command.command == "skill"
    assert command.name == "security__summarize"
    assert command.arguments == {"topic": "alerts"}


def test_parse_rejects_bad_json():
    with pytest.raises(SlashCommandError, match="Arguments must be a JSON object"):
        parse_slash_command("/tool security__lookup not-json")


def test_parse_rejects_extra_arguments_to_list_commands():
    with pytest.raises(SlashCommandError, match="does not accept arguments"):
        parse_slash_command("/tools extra")
