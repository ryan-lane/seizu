from pdpyras import APISession

from reporting import settings


_SESSION = None


def get_session() -> APISession:
    global _SESSION
    if _SESSION is None:
        _SESSION = APISession(settings.PAGERDUTY_API_KEY)
    return _SESSION
