import time

from pynamodb.exceptions import TableError

from reporting.models.user import User


# Based on:
# https://raw.githubusercontent.com/lyft/confidant/cc72f7d1ebea6e003127fb4d28778912b1a658f6/confidant/utils/dynamodb.py
def create_dynamodb_tables() -> None:
    i = 0
    # This loop is absurd, but there's race conditions with dynamodb local
    while i < 5:
        try:
            if not User.exists():
                User.create_table(
                    read_capacity_units=10,
                    write_capacity_units=10,
                    wait=True,
                )
            break
        except TableError:
            i = i + 1
            time.sleep(2)
