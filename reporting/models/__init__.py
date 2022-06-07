from reporting import settings
from reporting.utils.dynamodb import create_dynamodb_tables

if settings.DYNAMODB_CREATE_TABLE:
    create_dynamodb_tables()
