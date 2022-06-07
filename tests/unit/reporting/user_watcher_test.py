import neo4j.exceptions

from reporting import user_watcher


def test_watch_users(mocker):
    runner = user_watcher.app.test_cli_runner()
    mocker.patch(
        "reporting.user_watcher._is_shutdown",
        side_effect=[False, False, True, True],
    )
    bootstrap_mock = mocker.patch("reporting.user_watcher._bootstrap")
    delete_mock = mocker.patch(
        "reporting.services.reporting_neo4j.delete_expired_users",
        side_effect=[neo4j.exceptions.ServiceUnavailable, None],
    )
    sleep_mock = mocker.patch("time.sleep")
    runner.invoke(user_watcher.watch_users)
    assert bootstrap_mock.call_count == 1
    assert sleep_mock.call_count == 1
    assert delete_mock.call_count == 1
