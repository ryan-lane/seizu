from reporting.asgi import application


def test_app_created():
    assert application
