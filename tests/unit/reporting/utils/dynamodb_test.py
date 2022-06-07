from pynamodb.exceptions import TableError

import reporting.utils.dynamodb
from reporting.models.user import User


def test_create_dynamodb_tables(mocker):
    time_mock = mocker.patch("time.sleep")
    mocker.patch.object(User, "exists", side_effect=[TableError, False, True])
    create_mock = mocker.patch.object(User, "create_table", return_value=None)
    reporting.utils.dynamodb.create_dynamodb_tables()
    create_mock.assert_called_once()
    time_mock.assert_called_once()
