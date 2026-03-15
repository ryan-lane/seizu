from reporting.app import create_app


def test_config(mocker):
    mocker.patch(
        "reporting.settings.REPORTING_CONFIG_FILE",
        "tests/data/reporting-dashboard.conf",
    )
    settings = {
        "PREFERRED_URL_SCHEME": "https",
        "SECRET_KEY": "fake",
    }
    app = create_app(settings)
    client = app.test_client()
    ret = client.get("/api/v1/config", follow_redirects=False)
    assert ret.status_code == 200
    ret_json = ret.json
    assert ret_json["console_url"] == "http://localhost:7474"
    assert "auth_required" in ret_json
    for key in ["queries", "dashboard", "reports"]:
        assert key in ret_json["config"].keys()
    assert "$schema" in ret_json["schema"].keys()


def test_config_auth_required_true(mocker):
    mocker.patch(
        "reporting.settings.REPORTING_CONFIG_FILE",
        "tests/data/reporting-dashboard.conf",
    )
    mocker.patch("reporting.settings.DEVELOPMENT_ONLY_REQUIRE_AUTH", True)
    app = create_app({"PREFERRED_URL_SCHEME": "https", "SECRET_KEY": "fake"})
    ret = app.test_client().get("/api/v1/config", follow_redirects=False)
    assert ret.json["auth_required"] is True


def test_config_auth_required_false(mocker):
    mocker.patch(
        "reporting.settings.REPORTING_CONFIG_FILE",
        "tests/data/reporting-dashboard.conf",
    )
    mocker.patch("reporting.settings.DEVELOPMENT_ONLY_REQUIRE_AUTH", False)
    app = create_app({"PREFERRED_URL_SCHEME": "https", "SECRET_KEY": "fake"})
    ret = app.test_client().get("/api/v1/config", follow_redirects=False)
    assert ret.json["auth_required"] is False
