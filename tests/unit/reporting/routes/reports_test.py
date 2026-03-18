from reporting.app import create_app
from reporting.schema.report_config import ReportListItem
from reporting.schema.report_config import ReportVersion


def _app_settings():
    return {
        "PREFERRED_URL_SCHEME": "https",
        "SECRET_KEY": "fake",
    }


def _make_app(mocker):
    mocker.patch("reporting.settings.CSRF_DISABLE", True)
    mocker.patch(
        "reporting.routes.reports.authnz.get_email",
        return_value="user@example.com",
    )
    mocker.patch("reporting.settings.DYNAMODB_CREATE_TABLE", False)
    return create_app(_app_settings())


def _report_list_item(report_id="rid1", name="My Report", current_version=1):
    return ReportListItem(
        report_id=report_id,
        name=name,
        current_version=current_version,
        created_at="2024-01-01T00:00:00+00:00",
        updated_at="2024-01-01T00:00:00+00:00",
    )


def _report_version(report_id="rid1", version=1):
    return ReportVersion(
        report_id=report_id,
        name="My Report",
        version=version,
        config={"rows": []},
        created_at="2024-01-01T00:00:00+00:00",
        created_by="user@example.com",
        comment=None,
    )


# ---------------------------------------------------------------------------
# GET /api/v1/reports
# ---------------------------------------------------------------------------


def test_list_reports_success(mocker):
    app = _make_app(mocker)
    mocker.patch(
        "reporting.routes.reports.report_store.list_reports",
        return_value=[_report_list_item()],
    )
    ret = app.test_client().get("/api/v1/reports")
    assert ret.status_code == 200
    reports = ret.json["reports"]
    assert len(reports) == 1
    assert reports[0]["report_id"] == "rid1"
    assert reports[0]["name"] == "My Report"
    assert reports[0]["current_version"] == 1


def test_list_reports_empty(mocker):
    app = _make_app(mocker)
    mocker.patch(
        "reporting.routes.reports.report_store.list_reports",
        return_value=[],
    )
    ret = app.test_client().get("/api/v1/reports")
    assert ret.status_code == 200
    assert ret.json["reports"] == []


# ---------------------------------------------------------------------------
# GET /api/v1/reports/dashboard
# ---------------------------------------------------------------------------


def test_get_dashboard_report_success(mocker):
    app = _make_app(mocker)
    mocker.patch(
        "reporting.routes.reports.report_store.get_dashboard_report",
        return_value=_report_version(),
    )
    ret = app.test_client().get("/api/v1/reports/dashboard")
    assert ret.status_code == 200
    assert ret.json["report_id"] == "rid1"
    assert ret.json["version"] == 1


def test_get_dashboard_report_not_configured(mocker):
    app = _make_app(mocker)
    mocker.patch(
        "reporting.routes.reports.report_store.get_dashboard_report",
        return_value=None,
    )
    ret = app.test_client().get("/api/v1/reports/dashboard")
    assert ret.status_code == 404
    assert "dashboard" in ret.json["error"].lower()


# ---------------------------------------------------------------------------
# PUT /api/v1/reports/<report_id>/dashboard
# ---------------------------------------------------------------------------


def test_set_dashboard_report_success(mocker):
    app = _make_app(mocker)
    mocker.patch(
        "reporting.routes.reports.report_store.set_dashboard_report",
        return_value=True,
    )
    ret = app.test_client().put("/api/v1/reports/rid1/dashboard")
    assert ret.status_code == 200
    assert ret.json["report_id"] == "rid1"


def test_set_dashboard_report_not_found(mocker):
    app = _make_app(mocker)
    mocker.patch(
        "reporting.routes.reports.report_store.set_dashboard_report",
        return_value=False,
    )
    ret = app.test_client().put("/api/v1/reports/missing/dashboard")
    assert ret.status_code == 404
    assert "not found" in ret.json["error"].lower()


# ---------------------------------------------------------------------------
# GET /api/v1/reports/<report_id>
# ---------------------------------------------------------------------------


def test_get_report_success(mocker):
    app = _make_app(mocker)
    mocker.patch(
        "reporting.routes.reports.report_store.get_report_latest",
        return_value=_report_version(),
    )
    ret = app.test_client().get("/api/v1/reports/rid1")
    assert ret.status_code == 200
    assert ret.json["report_id"] == "rid1"
    assert ret.json["version"] == 1
    assert ret.json["config"] == {"rows": []}


def test_get_report_not_found(mocker):
    app = _make_app(mocker)
    mocker.patch(
        "reporting.routes.reports.report_store.get_report_latest",
        return_value=None,
    )
    ret = app.test_client().get("/api/v1/reports/missing")
    assert ret.status_code == 404
    assert "not found" in ret.json["error"].lower()


# ---------------------------------------------------------------------------
# GET /api/v1/reports/<report_id>/versions
# ---------------------------------------------------------------------------


def test_list_versions_success(mocker):
    app = _make_app(mocker)
    mocker.patch(
        "reporting.routes.reports.report_store.list_report_versions",
        return_value=[_report_version(version=2), _report_version(version=1)],
    )
    ret = app.test_client().get("/api/v1/reports/rid1/versions")
    assert ret.status_code == 200
    versions = ret.json["versions"]
    assert len(versions) == 2
    assert versions[0]["version"] == 2
    assert versions[1]["version"] == 1


def test_list_versions_report_not_found(mocker):
    app = _make_app(mocker)
    mocker.patch(
        "reporting.routes.reports.report_store.list_report_versions",
        return_value=[],
    )
    ret = app.test_client().get("/api/v1/reports/missing/versions")
    assert ret.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/v1/reports/<report_id>/versions/<version_num>
# ---------------------------------------------------------------------------


def test_get_version_success(mocker):
    app = _make_app(mocker)
    mocker.patch(
        "reporting.routes.reports.report_store.get_report_version",
        return_value=_report_version(version=3),
    )
    ret = app.test_client().get("/api/v1/reports/rid1/versions/3")
    assert ret.status_code == 200
    assert ret.json["version"] == 3


def test_get_version_not_found(mocker):
    app = _make_app(mocker)
    mocker.patch(
        "reporting.routes.reports.report_store.get_report_version",
        return_value=None,
    )
    ret = app.test_client().get("/api/v1/reports/rid1/versions/99")
    assert ret.status_code == 404
    assert "not found" in ret.json["error"].lower()


# ---------------------------------------------------------------------------
# POST /api/v1/reports
# ---------------------------------------------------------------------------


def test_create_report_success(mocker):
    app = _make_app(mocker)
    mocker.patch(
        "reporting.routes.reports.report_store.create_report",
        return_value=_report_list_item(),
    )
    ret = app.test_client().post(
        "/api/v1/reports",
        json={"name": "My Report"},
    )
    assert ret.status_code == 201
    assert ret.json["report_id"] == "rid1"
    assert ret.json["name"] == "My Report"
    assert ret.json["current_version"] == 1


def test_create_report_passes_fields_to_service(mocker):
    app = _make_app(mocker)
    mock_create = mocker.patch(
        "reporting.routes.reports.report_store.create_report",
        return_value=_report_list_item(),
    )
    app.test_client().post(
        "/api/v1/reports",
        json={"name": "My Report"},
    )
    mock_create.assert_called_once_with(
        name="My Report",
        created_by="user@example.com",
    )


def test_create_report_missing_required_fields(mocker):
    app = _make_app(mocker)
    ret = app.test_client().post(
        "/api/v1/reports",
        json={},
    )
    assert ret.status_code == 400
    assert "Invalid request" in ret.json["error"]


def test_create_report_non_json_body(mocker):
    app = _make_app(mocker)
    ret = app.test_client().post(
        "/api/v1/reports",
        data="not json",
        content_type="text/plain",
    )
    assert ret.status_code == 400
    assert "Request must be JSON" in ret.json["error"]


# ---------------------------------------------------------------------------
# POST /api/v1/reports/<report_id>/versions
# ---------------------------------------------------------------------------


def test_create_version_success(mocker):
    app = _make_app(mocker)
    mocker.patch(
        "reporting.routes.reports.report_store.save_report_version",
        return_value=_report_version(version=2),
    )
    ret = app.test_client().post(
        "/api/v1/reports/rid1/versions",
        json={"config": {"rows": []}, "comment": "v2"},
    )
    assert ret.status_code == 201
    assert ret.json["version"] == 2


def test_create_version_passes_fields_to_service(mocker):
    app = _make_app(mocker)
    mock_save = mocker.patch(
        "reporting.routes.reports.report_store.save_report_version",
        return_value=_report_version(version=2),
    )
    app.test_client().post(
        "/api/v1/reports/rid1/versions",
        json={"config": {"rows": [{"name": "r"}]}, "comment": "update"},
    )
    mock_save.assert_called_once_with(
        report_id="rid1",
        config={"rows": [{"name": "r"}]},
        created_by="user@example.com",
        comment="update",
    )


def test_create_version_report_not_found(mocker):
    app = _make_app(mocker)
    mocker.patch(
        "reporting.routes.reports.report_store.save_report_version",
        return_value=None,
    )
    ret = app.test_client().post(
        "/api/v1/reports/missing/versions",
        json={"config": {}},
    )
    assert ret.status_code == 404
    assert "not found" in ret.json["error"].lower()


def test_create_version_missing_config_field(mocker):
    app = _make_app(mocker)
    ret = app.test_client().post(
        "/api/v1/reports/rid1/versions",
        json={"comment": "no config"},
    )
    assert ret.status_code == 400
    assert "Invalid request" in ret.json["error"]


def test_create_version_non_json_body(mocker):
    app = _make_app(mocker)
    ret = app.test_client().post(
        "/api/v1/reports/rid1/versions",
        data="not json",
        content_type="text/plain",
    )
    assert ret.status_code == 400
    assert "Request must be JSON" in ret.json["error"]


# ---------------------------------------------------------------------------
# DELETE /api/v1/reports/<report_id>
# ---------------------------------------------------------------------------


def test_delete_report_success(mocker):
    app = _make_app(mocker)
    mocker.patch(
        "reporting.routes.reports.report_store.delete_report",
        return_value=True,
    )
    ret = app.test_client().delete("/api/v1/reports/rid1")
    assert ret.status_code == 200
    assert ret.json["report_id"] == "rid1"


def test_delete_report_not_found(mocker):
    app = _make_app(mocker)
    mocker.patch(
        "reporting.routes.reports.report_store.delete_report",
        return_value=False,
    )
    ret = app.test_client().delete("/api/v1/reports/missing")
    assert ret.status_code == 404
    assert "not found" in ret.json["error"].lower()
