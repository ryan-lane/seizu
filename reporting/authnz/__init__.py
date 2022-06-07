import logging
from typing import Dict
from typing import Union

import jwt
import requests
from flask import request
from jwt.algorithms import Algorithm
from jwt.api_jwk import PyJWKSet

from reporting import settings

logger = logging.getLogger(__name__)

# TODO(ryan-lane): add custom exceptions and exception handling


def _get_key(token: str) -> Union[Algorithm, bytes]:
    # TODO (ryan-lane): memoize this
    url = settings.JWKS_URL
    token_headers = jwt.get_unverified_header(token)
    kid = token_headers["kid"]
    url = url.format(AWS_DEFAULT_REGION=settings.AWS_DEFAULT_REGION, kid=kid)
    logger.debug("JWKS_URL", extra={"url": url, "kid": kid})
    req = requests.get(url)
    logger.debug(
        "jwks response",
        extra={"status_code": req.status_code, "text": req.text},
    )
    pub_key = None
    if settings.JWKS_URL_FOR_ALB:
        # Abnormal JWKS: -----BEGIN PUBLIC KEY-----...\n
        pub_key = req.content
    else:
        # Standard JWKS: {'keys': [...]}
        key_set = PyJWKSet.from_dict(req.json())
        for key in key_set.keys:
            # Typing incorrectly identifies this
            if key.key_id == kid:  # type: ignore
                pub_key = key.key
                break
    if pub_key is None:
        raise Exception()
    return pub_key


def _get_jwt_payload() -> Dict:
    """
    Get the jwt payload data from the request headers
    """
    headers = request.headers

    # Get the key id from JWT headers (the kid field)
    encoded_jwt = headers.get("x-amzn-oidc-data")
    if not encoded_jwt:
        # TODO(ryan-lane): Add custom exception for this
        raise Exception()
    # Get the public key from regional endpoint
    pub_key = _get_key(encoded_jwt)

    # Get the payload
    # Note: the type check here says the library expects a dict, but the docs say otherwise,
    # and functional testing shows this is correct.
    return jwt.decode(encoded_jwt, pub_key, algorithms=settings.ALLOWED_JWT_ALGORITHMS)  # type: ignore


def get_email() -> str:
    if not settings.DEVELOPMENT_ONLY_REQUIRE_AUTH:
        email = settings.DEVELOPMENT_ONLY_AUTH_USER_EMAIL
        logger.warning(
            "Authentication is disabled",
            extra={"type": "AUDIT", "user": email},
        )
        return email
    payload = _get_jwt_payload()
    email = payload["email"]
    return email
