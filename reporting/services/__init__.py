import logging
from typing import Any
from typing import Optional

import boto3

logger = logging.getLogger(__name__)


def get_boto_session(
    region: Optional[str],
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
    aws_session_token: Optional[str] = None,
) -> boto3.Session:
    """Get a boto3 session."""
    return boto3.Session(
        region_name=region,
        aws_secret_access_key=aws_secret_access_key,
        aws_access_key_id=aws_access_key_id,
        aws_session_token=aws_session_token,
    )


def get_boto_resource(
    resource: str,
    region: Optional[str] = None,
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
    endpoint_url: Optional[str] = None,
) -> Any:
    """Return a boto3 resource."""
    session = get_boto_session(region, aws_access_key_id, aws_secret_access_key)
    return session.resource(resource, endpoint_url=endpoint_url)


def get_boto_client(
    client: str,
    region: Optional[str] = None,
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
    aws_session_token: Optional[str] = None,
    endpoint_url: Optional[str] = None,
) -> Any:
    """Return a boto3 client."""
    session = get_boto_session(
        region, aws_access_key_id, aws_secret_access_key, aws_session_token
    )
    return session.client(client, endpoint_url=endpoint_url)
