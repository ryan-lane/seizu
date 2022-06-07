import logging

from reporting.scheduled_query_modules import log
from reporting.schema.reporting_config import ReportingConfig
from reporting.schema.reporting_config import ScheduledQuery
from reporting.schema.reporting_config import ScheduledQueryAction


def test_action_name():
    assert log.action_name() == "log"


def test_setup(mocker):
    # this function should do nothing, but we also want to make sure it
    # isn't failing.
    sq = {
        "test_query": ScheduledQuery(
            name="test_query",
            cypher="test",
            actions=[
                ScheduledQueryAction(
                    action_type="log",
                    action_config={
                        "message": "test",
                        "level": "info",
                        "log_attrs": ["id"],
                    },
                ),
            ],
        ),
    }
    config = ReportingConfig(scheduled_queries=sq)
    assert log.setup(config) is None


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
