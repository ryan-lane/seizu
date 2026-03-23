from unittest.mock import MagicMock

from reporting.app import create_app
from reporting.schema.report_config import User
from reporting.services.query_validator import ValidationResult

_FAKE_USER = User(
    user_id="test-user-id",
    sub="sub123",
    iss="https://idp.example.com",
    email="test@example.com",
    created_at="2024-01-01T00:00:00+00:00",
    last_login="2024-01-01T00:00:00+00:00",
)


def _app_settings():
    return {
        "PREFERRED_URL_SCHEME": "https",
    }


def _mock_validate(mocker, errors=None, warnings=None):
    result = ValidationResult(
        errors=errors if errors is not None else [],
        warnings=warnings if warnings is not None else [],
    )
    mocker.patch(
        "reporting.routes.query.validate_query",
        return_value=result,
    )
    return result


def test_query_success(mocker):
    mocker.patch("reporting.settings.CSRF_DISABLE", True)
    mocker.patch(
        "reporting.routes.query.authnz.get_user",
        return_value=_FAKE_USER,
    )
    _mock_validate(mocker)
    mock_record = MagicMock()
    mock_record.items.return_value = [("name", "Alice"), ("count", 42)]
    mocker.patch(
        "reporting.routes.query.reporting_neo4j.run_query",
        return_value=[mock_record],
    )

    app = create_app(_app_settings())
    client = app.test_client()
    ret = client.post(
        "/api/v1/query",
        json={"query": "MATCH (n) RETURN n.name AS name, count(n) AS count"},
    )
    assert ret.status_code == 200
    assert ret.json["results"] == [{"name": "Alice", "count": 42}]
    assert ret.json["errors"] == []
    assert ret.json["warnings"] == []


def test_query_success_with_warnings(mocker):
    mocker.patch("reporting.settings.CSRF_DISABLE", True)
    mocker.patch(
        "reporting.routes.query.authnz.get_user",
        return_value=_FAKE_USER,
    )
    _mock_validate(mocker, warnings=["Unknown label: Foo"])
    mock_record = MagicMock()
    mock_record.items.return_value = [("name", "Alice")]
    mocker.patch(
        "reporting.routes.query.reporting_neo4j.run_query",
        return_value=[mock_record],
    )

    app = create_app(_app_settings())
    client = app.test_client()
    ret = client.post(
        "/api/v1/query",
        json={"query": "MATCH (n:Foo) RETURN n.name AS name"},
    )
    assert ret.status_code == 200
    assert ret.json["results"] == [{"name": "Alice"}]
    assert ret.json["warnings"] == ["Unknown label: Foo"]
    assert ret.json["errors"] == []


def test_query_with_params(mocker):
    mocker.patch("reporting.settings.CSRF_DISABLE", True)
    mocker.patch(
        "reporting.routes.query.authnz.get_user",
        return_value=_FAKE_USER,
    )
    _mock_validate(mocker)
    mock_record = MagicMock()
    mock_record.items.return_value = [("name", "Alice")]
    mock_run_query = mocker.patch(
        "reporting.routes.query.reporting_neo4j.run_query",
        return_value=[mock_record],
    )

    app = create_app(_app_settings())
    client = app.test_client()
    ret = client.post(
        "/api/v1/query",
        json={
            "query": "MATCH (n) WHERE n.name = $name RETURN n.name AS name",
            "params": {"name": "Alice"},
        },
    )
    assert ret.status_code == 200
    mock_run_query.assert_called_once_with(
        "MATCH (n) WHERE n.name = $name RETURN n.name AS name",
        parameters={"name": "Alice"},
    )


def test_query_passes_params_to_validator(mocker):
    """validate_query must receive the request params so it can run EXPLAIN with them."""
    mocker.patch("reporting.settings.CSRF_DISABLE", True)
    mocker.patch(
        "reporting.routes.query.authnz.get_user",
        return_value=_FAKE_USER,
    )
    from reporting.services.query_validator import ValidationResult

    mock_validate = mocker.patch(
        "reporting.routes.query.validate_query",
        return_value=ValidationResult(),
    )
    mock_record = MagicMock()
    mock_record.items.return_value = [("name", "Alice")]
    mocker.patch(
        "reporting.routes.query.reporting_neo4j.run_query",
        return_value=[mock_record],
    )

    app = create_app(_app_settings())
    client = app.test_client()
    client.post(
        "/api/v1/query",
        json={
            "query": "MATCH (n) WHERE n.name = $name RETURN n.name AS name",
            "params": {"name": "Alice"},
        },
    )
    mock_validate.assert_called_once_with(
        "MATCH (n) WHERE n.name = $name RETURN n.name AS name",
        params={"name": "Alice"},
    )


def test_query_no_json_body(mocker):
    mocker.patch("reporting.settings.CSRF_DISABLE", True)
    mocker.patch(
        "reporting.routes.query.authnz.get_user",
        return_value=_FAKE_USER,
    )

    app = create_app(_app_settings())
    client = app.test_client()
    ret = client.post(
        "/api/v1/query",
        data="not json",
        content_type="text/plain",
    )
    assert ret.status_code == 400
    assert ret.json["error"]


def test_query_missing_query_field(mocker):
    mocker.patch("reporting.settings.CSRF_DISABLE", True)
    mocker.patch(
        "reporting.routes.query.authnz.get_user",
        return_value=_FAKE_USER,
    )

    app = create_app(_app_settings())
    client = app.test_client()
    ret = client.post(
        "/api/v1/query",
        json={"params": {"name": "Alice"}},
    )
    assert ret.status_code == 400
    assert ret.json["error"]


def test_query_validation_errors_return_400_with_errors_and_warnings(mocker):
    mocker.patch("reporting.settings.CSRF_DISABLE", True)
    mocker.patch(
        "reporting.routes.query.authnz.get_user",
        return_value=_FAKE_USER,
    )
    _mock_validate(mocker, errors=["Write queries are not allowed"])

    app = create_app(_app_settings())
    client = app.test_client()
    ret = client.post(
        "/api/v1/query",
        json={"query": "CREATE (n) RETURN n"},
    )
    assert ret.status_code == 400
    assert ret.json["errors"] == ["Write queries are not allowed"]
    assert "warnings" in ret.json


def test_query_validation_errors_do_not_execute_query(mocker):
    mocker.patch("reporting.settings.CSRF_DISABLE", True)
    mocker.patch(
        "reporting.routes.query.authnz.get_user",
        return_value=_FAKE_USER,
    )
    _mock_validate(mocker, errors=["Write queries are not allowed"])
    mock_run = mocker.patch("reporting.routes.query.reporting_neo4j.run_query")

    app = create_app(_app_settings())
    client = app.test_client()
    client.post("/api/v1/query", json={"query": "CREATE (n) RETURN n"})

    mock_run.assert_not_called()


def test_query_execution_failure(mocker):
    mocker.patch("reporting.settings.CSRF_DISABLE", True)
    mocker.patch(
        "reporting.routes.query.authnz.get_user",
        return_value=_FAKE_USER,
    )
    _mock_validate(mocker)
    mocker.patch(
        "reporting.routes.query.reporting_neo4j.run_query",
        side_effect=Exception("Connection refused"),
    )

    app = create_app(_app_settings())
    client = app.test_client()
    ret = client.post(
        "/api/v1/query",
        json={"query": "MATCH (n) RETURN n"},
    )
    assert ret.status_code == 500
    assert "Query execution failed" in ret.json["error"]


def test_query_no_csrf(mocker):
    mocker.patch("reporting.settings.CSRF_DISABLE", False)
    mocker.patch("reporting.settings.SECRET_KEY", "fake")
    mocker.patch(
        "reporting.routes.query.authnz.get_user",
        return_value=_FAKE_USER,
    )

    app = create_app(_app_settings())
    client = app.test_client()
    ret = client.post(
        "/api/v1/query",
        json={"query": "MATCH (n) RETURN n"},
    )
    assert ret.status_code == 403


def test_query_with_csrf(mocker, helpers):
    mocker.patch("reporting.settings.CSRF_DISABLE", False)
    mocker.patch("reporting.settings.SECRET_KEY", "fake")
    mocker.patch(
        "reporting.routes.query.authnz.get_user",
        return_value=_FAKE_USER,
    )
    _mock_validate(mocker)
    mock_record = MagicMock()
    mock_record.items.return_value = [("n", 1)]
    mocker.patch(
        "reporting.routes.query.reporting_neo4j.run_query",
        return_value=[mock_record],
    )

    app = create_app(_app_settings())
    with app.test_client() as client:
        ret = client.get("/index.html")
        cookie_name = app.config["CSRF_COOKIE_NAME"]
        cookie_header = app.config["CSRF_HEADER_NAME"]
        cookie = helpers.get_cookie(ret, cookie_name)
        ret = client.post(
            "/api/v1/query",
            json={"query": "MATCH (n) RETURN n LIMIT 1"},
            headers={
                cookie_header: cookie,
                "Referer": "https://localhost",
            },
        )
        assert ret.status_code == 200


def test_query_serialize_node(mocker):
    mocker.patch("reporting.settings.CSRF_DISABLE", True)
    mocker.patch(
        "reporting.routes.query.authnz.get_user",
        return_value=_FAKE_USER,
    )
    _mock_validate(mocker)

    from neo4j.graph import Node

    mock_node = MagicMock(spec=Node)
    mock_node.id = 123
    mock_node.labels = frozenset(["Person"])
    mock_node.items.return_value = [("name", "Alice")]

    mock_record = MagicMock()
    mock_record.items.return_value = [("n", mock_node)]

    mocker.patch(
        "reporting.routes.query.reporting_neo4j.run_query",
        return_value=[mock_record],
    )

    app = create_app(_app_settings())
    client = app.test_client()
    ret = client.post(
        "/api/v1/query",
        json={"query": "MATCH (n:Person) RETURN n LIMIT 1"},
    )
    assert ret.status_code == 200
    result = ret.json["results"][0]["n"]
    assert result["id"] == 123
    assert result["labels"] == ["Person"]
    assert result["properties"]["name"] == "Alice"


def test_query_serialize_relationship(mocker):
    mocker.patch("reporting.settings.CSRF_DISABLE", True)
    mocker.patch(
        "reporting.routes.query.authnz.get_user",
        return_value=_FAKE_USER,
    )
    _mock_validate(mocker)

    from neo4j.graph import Node
    from neo4j.graph import Relationship

    mock_start = MagicMock(spec=Node)
    mock_start.id = 1
    mock_end = MagicMock(spec=Node)
    mock_end.id = 2

    mock_rel = MagicMock(spec=Relationship)
    mock_rel.id = 456
    mock_rel.type = "KNOWS"
    mock_rel.start_node = mock_start
    mock_rel.end_node = mock_end
    mock_rel.items.return_value = [("since", 2020)]

    mock_record = MagicMock()
    mock_record.items.return_value = [("r", mock_rel)]

    mocker.patch(
        "reporting.routes.query.reporting_neo4j.run_query",
        return_value=[mock_record],
    )

    app = create_app(_app_settings())
    client = app.test_client()
    ret = client.post(
        "/api/v1/query",
        json={"query": "MATCH ()-[r:KNOWS]->() RETURN r LIMIT 1"},
    )
    assert ret.status_code == 200
    result = ret.json["results"][0]["r"]
    assert result["id"] == 456
    assert result["type"] == "KNOWS"
    assert result["start_node_id"] == 1
    assert result["end_node_id"] == 2
    assert result["properties"]["since"] == 2020


def test_query_serialize_path(mocker):
    mocker.patch("reporting.settings.CSRF_DISABLE", True)
    mocker.patch(
        "reporting.routes.query.authnz.get_user",
        return_value=_FAKE_USER,
    )
    _mock_validate(mocker)

    from neo4j.graph import Node
    from neo4j.graph import Path
    from neo4j.graph import Relationship

    mock_node1 = MagicMock(spec=Node)
    mock_node1.id = 1
    mock_node1.labels = frozenset(["Person"])
    mock_node1.items.return_value = [("name", "Alice")]

    mock_node2 = MagicMock(spec=Node)
    mock_node2.id = 2
    mock_node2.labels = frozenset(["Person"])
    mock_node2.items.return_value = [("name", "Bob")]

    mock_rel = MagicMock(spec=Relationship)
    mock_rel.id = 10
    mock_rel.type = "KNOWS"
    mock_rel.start_node = mock_node1
    mock_rel.end_node = mock_node2
    mock_rel.items.return_value = []

    mock_path = MagicMock(spec=Path)
    mock_path.nodes = [mock_node1, mock_node2]
    mock_path.relationships = [mock_rel]

    mock_record = MagicMock()
    mock_record.items.return_value = [("p", mock_path)]

    mocker.patch(
        "reporting.routes.query.reporting_neo4j.run_query",
        return_value=[mock_record],
    )

    app = create_app(_app_settings())
    client = app.test_client()
    ret = client.post(
        "/api/v1/query",
        json={"query": "MATCH p=shortestPath((a)-[*]-(b)) RETURN p LIMIT 1"},
    )
    assert ret.status_code == 200
    result = ret.json["results"][0]["p"]
    assert len(result["nodes"]) == 2
    assert len(result["relationships"]) == 1
    assert result["nodes"][0]["properties"]["name"] == "Alice"
