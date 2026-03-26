import pytest


class Helpers:
    @staticmethod
    def get_cookie(response: object, cookie_name: str) -> str | None:
        """Extract a cookie value from an httpx response."""
        cookies = getattr(response, "cookies", {})
        return cookies.get(cookie_name)


@pytest.fixture
def helpers() -> type:
    return Helpers
