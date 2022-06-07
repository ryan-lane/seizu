from reporting.services import reporting_pagerduty


def test_get_session(mocker):
    # Ensure the object is cached after the first call. We're mocking the session as two
    # different strings, but only the first string should ever be returned.
    mocker.patch.object(
        reporting_pagerduty, "APISession", side_effect=["object A", "object B"]
    )
    a = reporting_pagerduty.get_session()
    b = reporting_pagerduty.get_session()

    assert a == b
