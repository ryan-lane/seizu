import pytest
from werkzeug.http import parse_cookie


class Helpers:
    @staticmethod
    def get_cookie(response, cookie_name):
        cookies = response.headers.getlist("Set-Cookie")
        for cookie in cookies:
            value = parse_cookie(cookie).get(cookie_name)
            if value:
                return value
        return None


@pytest.fixture
def helpers():
    return Helpers
