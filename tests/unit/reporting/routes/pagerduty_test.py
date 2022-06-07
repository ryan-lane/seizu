import reporting.routes.pagerduty
from reporting.app import create_app

ITER_ALL_DATA = [
    {
        "user": {
            "id": "PT23IWX",
            "type": "user_reference",
            "summary": "Tim Wright",
            "self": "https://api.pagerduty.com/users/PT23IWX",
            "html_url": "https://subdomain.pagerduty.com/users/PT23IWX",
        },
        "schedule": {
            "id": "PI7DH85",
            "type": "schedule_reference",
            "summary": "Daily Engineering Rotation",
            "self": "https://api.pagerduty.com/schedules/PI7DH85",
            "html_url": "https://subdomain.pagerduty.com/schedules/PI7DH85",
        },
        "escalation_policy": {
            "id": "PT20YPA",
            "type": "escalation_policy_reference",
            "summary": "Engineering Escalation Policy",
            "self": "https://api.pagerduty.com/escalation_policies/PT20YPA",
            "html_url": "https://subdomain.pagerduty.com/escalation_policies/PT20YPA",
        },
        "escalation_level": 2,
        "start": "2015-03-06T15:28:51-05:00",
        "end": "2015-03-07T15:28:51-05:00",
    }
]


def test_get_oncalls(mocker):
    iter_mock = mocker.Mock()
    iter_mock.iter_all.return_value = ITER_ALL_DATA
    session_mock = mocker.patch.object(reporting.routes.pagerduty, "get_session")
    session_mock.return_value = iter_mock
    mocker.patch("reporting.settings.SECRET_KEY", "fake")
    settings = {
        "PREFERRED_URL_SCHEME": "https",
    }
    app = create_app(settings)
    client = app.test_client()
    ret = client.get("/api/v1/pagerduty/oncalls", follow_redirects=False)
    iter_mock.iter_all.assert_called_with("oncalls", params={})
    assert ret.status_code == 200
    assert ret.json == {"oncalls": ITER_ALL_DATA}


def test_get_oncalls_with_params(mocker):
    iter_mock = mocker.Mock()
    iter_mock.iter_all.return_value = ITER_ALL_DATA
    session_mock = mocker.patch.object(reporting.routes.pagerduty, "get_session")
    session_mock.return_value = iter_mock
    mocker.patch("reporting.settings.SECRET_KEY", "fake")
    settings = {
        "PREFERRED_URL_SCHEME": "https",
    }
    app = create_app(settings)
    client = app.test_client()
    ret = client.get(
        "/api/v1/pagerduty/oncalls?user_ids=a,b&escalation_policy_ids=aa,bb&schedule_ids=aaa,bbb",
        follow_redirects=False,
    )
    iter_mock.iter_all.assert_called_with(
        "oncalls",
        params={
            "user_ids[]": ["a", "b"],
            "escalation_policy_ids[]": ["aa", "bb"],
            "schedule_ids[]": ["aaa", "bbb"],
        },
    )
    assert ret.status_code == 200
    assert ret.json == {"oncalls": ITER_ALL_DATA}
