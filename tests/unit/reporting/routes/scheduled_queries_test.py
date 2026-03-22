import json

from reporting.app import create_app
from reporting.schema.report_config import ScheduledQueryItem
from reporting.schema.report_config import ScheduledQueryVersion
from reporting.schema.report_config import User

_FAKE_USER = User(
    user_id="test-user-id",
    sub="sub123",
    iss="https://idp.example.com",
    email="user@example.com",
    display_name="Test User",
    created_at="2024-01-01T00:00:00+00:00",
    last_login="2024-01-01T00:00:00+00:00",
)

_SQ_ID = "sq-abc123"


def _app_settings():
    return {
        "PREFERRED_URL_SCHEME": "https",
        "SECRET_KEY": "fake",
    }


def _make_app(mocker):
    mocker.patch("reporting.settings.CSRF_DISABLE", True)
    mocker.patch(
        "reporting.routes.scheduled_queries.authnz.get_user",
        return_value=_FAKE_USER,
    )
    return create_app(_app_settings())


def _sq_item(sq_id=_SQ_ID, name="My Query", version=1):
    return ScheduledQueryItem(
        scheduled_query_id=sq_id,
        name=name,
        cypher="MATCH (n) RETURN n",
        frequency=60,
        enabled=True,
        actions=[{"action_type": "log", "action_config": {}}],
        current_version=version,
        created_at="2024-01-01T00:00:00+00:00",
        updated_at="2024-01-01T00:00:00+00:00",
        created_by="user@example.com",
    )


def _sq_version(sq_id=_SQ_ID, version=1):
    return ScheduledQueryVersion(
        scheduled_query_id=sq_id,
        name="My Query",
        version=version,
        cypher="MATCH (n) RETURN n",
        frequency=60,
        enabled=True,
        actions=[{"action_type": "log", "action_config": {}}],
        created_at="2024-01-01T00:00:00+00:00",
        created_by="user@example.com",
        comment="Initial version",
    )


_VALID_SQ_BODY = {
    "name": "My Query",
    "cypher": "MATCH (n) RETURN n",
    "frequency": 60,
    "enabled": True,
    "actions": [{"action_type": "log", "action_config": {}}],
}


# ---------------------------------------------------------------------------
# GET /api/v1/scheduled-queries
# ---------------------------------------------------------------------------


def test_list_scheduled_queries_success(mocker):
    app = _make_app(mocker)
    mocker.patch(
        "reporting.routes.scheduled_queries.report_store.list_scheduled_queries",
        return_value=[_sq_item()],
    )
    ret = app.test_client().get("/api/v1/scheduled-queries")
    assert ret.status_code == 200
    items = ret.json["scheduled_queries"]
    assert len(items) == 1
    assert items[0]["scheduled_query_id"] == _SQ_ID
    assert items[0]["name"] == "My Query"


def test_list_scheduled_queries_empty(mocker):
    app = _make_app(mocker)
    mocker.patch(
        "reporting.routes.scheduled_queries.report_store.list_scheduled_queries",
        return_value=[],
    )
    ret = app.test_client().get("/api/v1/scheduled-queries")
    assert ret.status_code == 200
    assert ret.json["scheduled_queries"] == []


# ---------------------------------------------------------------------------
# GET /api/v1/scheduled-queries/<sq_id>
# ---------------------------------------------------------------------------


def test_get_scheduled_query_success(mocker):
    app = _make_app(mocker)
    mocker.patch(
        "reporting.routes.scheduled_queries.report_store.get_scheduled_query",
        return_value=_sq_item(),
    )
    ret = app.test_client().get(f"/api/v1/scheduled-queries/{_SQ_ID}")
    assert ret.status_code == 200
    assert ret.json["scheduled_query_id"] == _SQ_ID


def test_get_scheduled_query_not_found(mocker):
    app = _make_app(mocker)
    mocker.patch(
        "reporting.routes.scheduled_queries.report_store.get_scheduled_query",
        return_value=None,
    )
    ret = app.test_client().get(f"/api/v1/scheduled-queries/{_SQ_ID}")
    assert ret.status_code == 404
    assert "error" in ret.json


# ---------------------------------------------------------------------------
# POST /api/v1/scheduled-queries
# ---------------------------------------------------------------------------


def test_create_scheduled_query_success(mocker):
    app = _make_app(mocker)
    mocker.patch(
        "reporting.routes.scheduled_queries.report_store.create_scheduled_query",
        return_value=_sq_item(),
    )
    mocker.patch(
        "reporting.routes.scheduled_queries.scheduled_query_modules.get_action_schemas",
        return_value={},
    )
    ret = app.test_client().post(
        "/api/v1/scheduled-queries",
        data=json.dumps(_VALID_SQ_BODY),
        content_type="application/json",
    )
    assert ret.status_code == 201
    assert ret.json["scheduled_query_id"] == _SQ_ID


def test_create_scheduled_query_not_json(mocker):
    app = _make_app(mocker)
    ret = app.test_client().post(
        "/api/v1/scheduled-queries",
        data="not json",
        content_type="text/plain",
    )
    assert ret.status_code == 400
    assert "error" in ret.json


def test_create_scheduled_query_invalid_body(mocker):
    app = _make_app(mocker)
    mocker.patch(
        "reporting.routes.scheduled_queries.scheduled_query_modules.get_action_schemas",
        return_value={},
    )
    ret = app.test_client().post(
        "/api/v1/scheduled-queries",
        data=json.dumps({"invalid": "body"}),
        content_type="application/json",
    )
    assert ret.status_code == 400
    assert "error" in ret.json


def test_create_scheduled_query_action_config_error(mocker):
    app = _make_app(mocker)
    from reporting.schema.report_config import ActionConfigFieldDef

    mocker.patch(
        "reporting.routes.scheduled_queries.scheduled_query_modules.get_action_schemas",
        return_value={
            "log": [
                ActionConfigFieldDef(
                    name="target", label="Target", type="string", required=True
                )
            ]
        },
    )
    body = dict(_VALID_SQ_BODY)
    body["actions"] = [{"action_type": "log", "action_config": {}}]
    ret = app.test_client().post(
        "/api/v1/scheduled-queries",
        data=json.dumps(body),
        content_type="application/json",
    )
    assert ret.status_code == 400
    assert "error" in ret.json


# ---------------------------------------------------------------------------
# PUT /api/v1/scheduled-queries/<sq_id>
# ---------------------------------------------------------------------------


def test_update_scheduled_query_success(mocker):
    app = _make_app(mocker)
    mocker.patch(
        "reporting.routes.scheduled_queries.report_store.update_scheduled_query",
        return_value=_sq_item(version=2),
    )
    mocker.patch(
        "reporting.routes.scheduled_queries.scheduled_query_modules.get_action_schemas",
        return_value={},
    )
    ret = app.test_client().put(
        f"/api/v1/scheduled-queries/{_SQ_ID}",
        data=json.dumps(_VALID_SQ_BODY),
        content_type="application/json",
    )
    assert ret.status_code == 200
    assert ret.json["current_version"] == 2


def test_update_scheduled_query_not_found(mocker):
    app = _make_app(mocker)
    mocker.patch(
        "reporting.routes.scheduled_queries.report_store.update_scheduled_query",
        return_value=None,
    )
    mocker.patch(
        "reporting.routes.scheduled_queries.scheduled_query_modules.get_action_schemas",
        return_value={},
    )
    ret = app.test_client().put(
        f"/api/v1/scheduled-queries/{_SQ_ID}",
        data=json.dumps(_VALID_SQ_BODY),
        content_type="application/json",
    )
    assert ret.status_code == 404


def test_update_scheduled_query_not_json(mocker):
    app = _make_app(mocker)
    ret = app.test_client().put(
        f"/api/v1/scheduled-queries/{_SQ_ID}",
        data="not json",
        content_type="text/plain",
    )
    assert ret.status_code == 400


def test_update_scheduled_query_invalid_body(mocker):
    app = _make_app(mocker)
    mocker.patch(
        "reporting.routes.scheduled_queries.scheduled_query_modules.get_action_schemas",
        return_value={},
    )
    ret = app.test_client().put(
        f"/api/v1/scheduled-queries/{_SQ_ID}",
        data=json.dumps({"invalid": "body"}),
        content_type="application/json",
    )
    assert ret.status_code == 400


# ---------------------------------------------------------------------------
# GET /api/v1/scheduled-queries/<sq_id>/versions
# ---------------------------------------------------------------------------


def test_list_scheduled_query_versions_success(mocker):
    app = _make_app(mocker)
    mocker.patch(
        "reporting.routes.scheduled_queries.report_store.get_scheduled_query",
        return_value=_sq_item(),
    )
    mocker.patch(
        "reporting.routes.scheduled_queries.report_store.list_scheduled_query_versions",
        return_value=[_sq_version(version=1), _sq_version(version=2)],
    )
    ret = app.test_client().get(f"/api/v1/scheduled-queries/{_SQ_ID}/versions")
    assert ret.status_code == 200
    versions = ret.json["versions"]
    assert len(versions) == 2
    assert versions[0]["version"] == 1


def test_list_scheduled_query_versions_not_found(mocker):
    app = _make_app(mocker)
    mocker.patch(
        "reporting.routes.scheduled_queries.report_store.get_scheduled_query",
        return_value=None,
    )
    ret = app.test_client().get(f"/api/v1/scheduled-queries/{_SQ_ID}/versions")
    assert ret.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/v1/scheduled-queries/<sq_id>/versions/<n>
# ---------------------------------------------------------------------------


def test_get_scheduled_query_version_success(mocker):
    app = _make_app(mocker)
    mocker.patch(
        "reporting.routes.scheduled_queries.report_store.get_scheduled_query_version",
        return_value=_sq_version(version=1),
    )
    ret = app.test_client().get(f"/api/v1/scheduled-queries/{_SQ_ID}/versions/1")
    assert ret.status_code == 200
    assert ret.json["version"] == 1
    assert ret.json["scheduled_query_id"] == _SQ_ID


def test_get_scheduled_query_version_not_found(mocker):
    app = _make_app(mocker)
    mocker.patch(
        "reporting.routes.scheduled_queries.report_store.get_scheduled_query_version",
        return_value=None,
    )
    ret = app.test_client().get(f"/api/v1/scheduled-queries/{_SQ_ID}/versions/99")
    assert ret.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/v1/scheduled-queries/<sq_id>
# ---------------------------------------------------------------------------


def test_delete_scheduled_query_success(mocker):
    app = _make_app(mocker)
    mocker.patch(
        "reporting.routes.scheduled_queries.report_store.delete_scheduled_query",
        return_value=True,
    )
    ret = app.test_client().delete(f"/api/v1/scheduled-queries/{_SQ_ID}")
    assert ret.status_code == 200
    assert ret.json["scheduled_query_id"] == _SQ_ID


def test_delete_scheduled_query_not_found(mocker):
    app = _make_app(mocker)
    mocker.patch(
        "reporting.routes.scheduled_queries.report_store.delete_scheduled_query",
        return_value=False,
    )
    ret = app.test_client().delete(f"/api/v1/scheduled-queries/{_SQ_ID}")
    assert ret.status_code == 404
