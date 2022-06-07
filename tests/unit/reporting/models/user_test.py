from datetime import datetime
from datetime import timedelta

from reporting import settings
from reporting.models.user import User


def test_expiration():
    u = User()
    u.password_set_date = datetime.now() - timedelta(
        seconds=settings.PASSWORD_EXPIRATION_TIME,
    )

    assert u.is_expired() is True
