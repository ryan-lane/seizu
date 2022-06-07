from reporting import utils


def test_bool_env(mocker):
    mocker.patch("reporting.utils.settings.getenv", return_value="False")
    assert utils.settings.bool_env("TEST") is False

    mocker.patch("reporting.utils.settings.getenv", return_value="false")
    assert utils.settings.bool_env("TEST") is False

    mocker.patch("reporting.utils.settings.getenv", return_value="0")
    assert utils.settings.bool_env("TEST") is False


def test_int_env(mocker):
    mocker.patch("reporting.utils.settings.getenv", return_value="1")
    assert utils.settings.int_env("TEST") == 1


def test_str_env(mocker):
    mocker.patch("reporting.utils.settings.getenv", return_value="test")
    assert utils.settings.str_env("TEST") == "test"


def test_list_env(mocker):
    mocker.patch("reporting.utils.settings.getenv", return_value="a,b")
    assert utils.settings.list_env("TEST") == ["a", "b"]

    mocker.patch("reporting.utils.settings.getenv", return_value=None)
    assert utils.settings.list_env("TEST") == []

    mocker.patch("reporting.utils.settings.getenv", return_value=None)
    assert utils.settings.list_env("TEST", ["a"]) == ["a"]
