from datetime import datetime
from datetime import timedelta

from pynamodb.attributes import UnicodeAttribute
from pynamodb.attributes import UTCDateTimeAttribute
from pynamodb.models import Model

from reporting import settings


class User(Model):
    class Meta:
        table_name = settings.DYNAMODB_TABLE
        if settings.DYNAMODB_URL:
            host = settings.DYNAMODB_URL
        region = settings.AWS_DEFAULT_REGION

    email = UnicodeAttribute(hash_key=True)
    password_set_date = UTCDateTimeAttribute(default=datetime.now)

    def is_expired(self) -> bool:
        expiration_date = self.password_set_date + timedelta(
            seconds=settings.PASSWORD_EXPIRATION_TIME,
        )
        # Need to remove the tzinfo to avoid comparing offset-naive and offset-aware datetimes
        return datetime.now() > expiration_date.replace(tzinfo=None)
