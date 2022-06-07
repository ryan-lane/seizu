from reporting import scheduled_query_modules


def test_load_modules(mocker):
    scheduled_query_modules.load_modules({})
    assert list(scheduled_query_modules._MODULES.keys()) == ["sqs", "slack"]
    assert scheduled_query_modules.get_module_names() == ["sqs", "slack"]
    assert scheduled_query_modules.get_module("sqs") is not None
