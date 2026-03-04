from __future__ import annotations

from functools import lru_cache
from typing import Any

import jwt


@lru_cache(maxsize=8)
def _get_jwks_client(jwks_url: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(jwks_url)


def verify_access_token(
    token: str,
    *,
    hs256_secret: str | None = None,
    jwks_url: str | None = None,
    issuer: str | None = None,
    audience: str | None = None,
) -> dict[str, Any]:
    """
    Verify a JWT using either:
    - HS256 (legacy/internal tokens) when the token alg is HS*
    - JWKS public keys (WorkOS/OIDC style) when token alg is RS*/ES*
    """
    header = jwt.get_unverified_header(token)
    algorithm = str(header.get("alg", "")).upper()
    if not algorithm:
        raise jwt.InvalidTokenError("Missing JWT alg header")

    base_options = {
        "require": ["sub", "exp"],
        "verify_exp": True,
    }

    if algorithm.startswith("HS"):
        if not hs256_secret or len(hs256_secret) < 32:
            raise jwt.InvalidTokenError("HS token validation unavailable")
        decode_kwargs_hs: dict[str, Any] = {
            "key": hs256_secret,
            "algorithms": [algorithm],
            "options": {**base_options},
        }
        if issuer:
            decode_kwargs_hs["issuer"] = issuer
        if audience:
            decode_kwargs_hs["audience"] = audience
        else:
            decode_kwargs_hs["options"]["verify_aud"] = False
        payload = jwt.decode(token, **decode_kwargs_hs)
    else:
        if not jwks_url:
            raise jwt.InvalidTokenError("JWKS URL not configured for asymmetric JWT validation")
        signing_key = _get_jwks_client(jwks_url).get_signing_key_from_jwt(token).key
        decode_kwargs: dict[str, Any] = {
            "key": signing_key,
            "algorithms": [algorithm],
            "options": {**base_options},
        }
        if issuer:
            decode_kwargs["issuer"] = issuer
        if audience:
            decode_kwargs["audience"] = audience
        else:
            decode_kwargs["options"]["verify_aud"] = False
        payload = jwt.decode(token, **decode_kwargs)

    if not payload.get("sub"):
        raise jwt.InvalidTokenError("Token missing subject")

    return payload
