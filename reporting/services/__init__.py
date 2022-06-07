import logging
from typing import Any
from typing import Dict
from typing import Optional

import boto3

logger = logging.getLogger(__name__)

CLIENT_CACHE: Dict[str, Any] = {}


def get_boto_client(
    client: str,
    region: Optional[str] = None,
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
    aws_session_token: Optional[str] = None,
    config: Dict[str, Any] = None,
    endpoint_url: Optional[str] = None,
) -> Any:
    """Get a boto3 client connection."""
    if config is None:
        config = {}
    cache_key = "{}:{}:{}:{}:{}".format(
        client, region, aws_access_key_id, config.get("name"), endpoint_url
    )
    if not aws_session_token:
        if cache_key in CLIENT_CACHE:
            return CLIENT_CACHE[cache_key]
    session = get_boto_session(
        region, aws_access_key_id, aws_secret_access_key, aws_session_token
    )
    if not session:
        logger.error(f"Failed to get {client} client.")
        return None

    CLIENT_CACHE[cache_key] = session.client(
        client, config=config.get("config"), endpoint_url=endpoint_url
    )
    return CLIENT_CACHE[cache_key]


def get_boto_session(
    region: Optional[str],
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
    aws_session_token: Optional[str] = None,
) -> Any:
    """Get a boto3 session."""
    return boto3.session.Session(
        region_name=region,
        aws_secret_access_key=aws_secret_access_key,
        aws_access_key_id=aws_access_key_id,
        aws_session_token=aws_session_token,
    )
