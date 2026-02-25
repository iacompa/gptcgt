# ruff: noqa: E501

import logging

import asyncpg
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from api.database import get_pool
from api.services.encryption import encrypt_key

logger = logging.getLogger(__name__)
router = APIRouter(tags=["api_keys"])


class CreateKeyRequest(BaseModel):
    provider: str
    key: str


@router.get("/")
async def list_keys(request: Request):
    """List all active API keys stored for the user."""
    workos_user_id = getattr(request.state, "user_id", None)
    if not workos_user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    pool = get_pool()

    # Internal UUID lookup
    internal_id = await pool.fetchval(
        "SELECT id FROM users WHERE workos_user_id = $1", workos_user_id
    )
    if not internal_id:
        raise HTTPException(status_code=404, detail="User not found")

    rows = await pool.fetch(
        """
        SELECT id, provider, is_active, created_at, encrypted_key
        FROM api_keys
        WHERE owner_type = 'user' AND owner_id = $1 AND is_active = true
        ORDER BY created_at DESC
        """,
        internal_id,
    )

    # We display a prefix hint based on the encrypted_key payload length or a static mock to
    # prevent decrypting just for the frontend display
    result = []
    for row in rows:
        result.append(
            {
                "id": row["id"],
                "provider": row["provider"],
                "key_prefix": "sk-...[encrypted]",
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                "is_active": row["is_active"],
            }
        )

    return result


@router.post("/")
async def create_key(req: CreateKeyRequest, request: Request):
    """Encrypt and store a user API key."""
    workos_user_id = getattr(request.state, "user_id", None)
    if not workos_user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if not req.key or len(req.key) < 10:
        raise HTTPException(status_code=400, detail="Invalid API key payload")

    pool = get_pool()
    internal_id = await pool.fetchval(
        "SELECT id FROM users WHERE workos_user_id = $1", workos_user_id
    )
    if not internal_id:
        raise HTTPException(status_code=404, detail="User not found")

    # Encrypt and Hash the raw key
    try:
        import hashlib

        encrypted = encrypt_key(req.key)
        key_hash = hashlib.sha256(req.key.encode()).hexdigest()
    except Exception as e:
        logger.error(f"Encryption failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to secure API key")

    # Insert
    row = await pool.fetchrow(
        """
        INSERT INTO api_keys (owner_type, owner_id, provider, encrypted_key, key_hash, is_active, created_at)  # noqa: E501
        VALUES ('user', $1, $2, $3, $4, true, now())
        RETURNING id, created_at
        """,
        internal_id,
        req.provider,
        encrypted.encode(),
        key_hash,
    )

    return {
        "id": row["id"],
        "provider": req.provider,
        "key_prefix": f"{req.key[:4]}...{req.key[-4:]}",
        "created_at": row["created_at"].isoformat(),
    }


@router.delete("/{key_id}")
async def revoke_key(key_id: str, request: Request):
    """Soft-delete an API key."""
    workos_user_id = getattr(request.state, "user_id", None)
    if not workos_user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    pool = get_pool()
    internal_id = await pool.fetchval(
        "SELECT id FROM users WHERE workos_user_id = $1", workos_user_id
    )

    try:
        # Ensure they own it
        result = await pool.execute(
            """
            UPDATE api_keys
            SET is_active = false
            WHERE id = $1 AND owner_type = 'user' AND owner_id = $2
            """,
            key_id,
            internal_id,
        )
        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail="Key not found or not owned by user")
    except asyncpg.exceptions.InvalidTextRepresentationError:
        raise HTTPException(status_code=400, detail="Invalid UUID format")

    return {"status": "success", "message": "Key revoked"}
