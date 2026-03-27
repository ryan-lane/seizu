import logging

from reporting.scheduled_query_modules import log
from reporting.schema.reporting_config import ScheduledQueryAction


def test_action_name():
    assert log.action_name() == "log"


async def test_setup():
    assert await log.setup() is None


def test_handle_results(caplog):
    action = ScheduledQueryAction(
        action_type="log",
        action_config={
            "message": "test",
            "level": "info",
            "log_attrs": ["id"],
        },
    )
    results = [{"details": {"id": "test"}}]
    with caplog.at_level(logging.INFO):
        log.handle_results("test_query", action, results)
    assert "test" in caplog.text
