import uuid
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from api.database import get_pool

router = APIRouter(tags=["team"])


class UserInfo(BaseModel):
    id: str
    email: str
    role: str
    allocated_quota: Optional[int]
    credits_remaining: Optional[int]
    billing_access: bool


class QuotaUpdateRequest(BaseModel):
    target_user_id: str
    new_quota: Optional[int]


class RoleUpdateRequest(BaseModel):
    target_user_id: str
    new_role: str  # 'admin' or 'member'


async def _get_requester_team_info(pool, workos_user_id: str):
    row = await pool.fetchrow(
        """
        SELECT u.id, u.team_id, u.team_role, t.name as team_name, t.shared_credits_remaining
        FROM users u
        JOIN teams t ON u.team_id = t.id
        WHERE u.workos_user_id = $1
    """,
        workos_user_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="User not found or not in a team")
    return row


@router.get("/", response_model=List[UserInfo])
async def get_team_members(request: Request, limit: int = 50, offset: int = 0):
    """Retrieve all members of the caller's team."""
    workos_user_id = getattr(request.state, "user_id", None)
    if not workos_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    pool = get_pool()
    async with pool.acquire() as conn:
        req_info = await _get_requester_team_info(conn, workos_user_id)

        # Admins and Owners can see everyone.
        if req_info["team_role"] not in ("owner", "admin"):
            raise HTTPException(status_code=403, detail="Forbidden")

        rows = await conn.fetch(
            """
            SELECT id, email, team_role, allocated_quota, credits_remaining, billing_access
            FROM users
            WHERE team_id = $1
            ORDER BY created_at ASC
            LIMIT $2 OFFSET $3
        """,
            req_info["team_id"], limit, offset
        )

        return [
            UserInfo(
                id=str(row["id"]),
                email=row["email"],
                role=row["team_role"],
                allocated_quota=row["allocated_quota"],
                credits_remaining=row["credits_remaining"],
                billing_access=row["billing_access"],
            )
            for row in rows
        ]


@router.patch("/quota")
async def update_member_quota(request: Request, body: QuotaUpdateRequest):
    """Update a specific member's usage quota."""
    workos_user_id = getattr(request.state, "user_id", None)
    if not workos_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    pool = get_pool()
    async with pool.acquire() as conn:
        req_info = await _get_requester_team_info(conn, workos_user_id)

        # Both Owners and Admins can update quotas.
        if req_info["team_role"] not in ("owner", "admin"):
            raise HTTPException(status_code=403, detail="Forbidden: You are not a Team Admin")

        # Verify the target user belongs to the same team
        try:
            target_uuid = uuid.UUID(body.target_user_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid user ID format")

        target_row = await conn.fetchrow(
            """
            SELECT team_id, team_role FROM users WHERE id = $1
        """,
            target_uuid,
        )

        if not target_row or target_row["team_id"] != req_info["team_id"]:
            raise HTTPException(status_code=400, detail="Target user not found on your team")

        # Admins cannot edit the Owner's quota
        if req_info["team_role"] == "admin" and target_row["team_role"] == "owner":
            raise HTTPException(status_code=403, detail="Admins cannot modify the Owner")

        await conn.execute(
            """
            UPDATE users SET allocated_quota = $1 WHERE id = $2
        """,
            body.new_quota,
            target_uuid,
        )

        return {"status": "success", "message": "Quota updated"}


@router.patch("/role")
async def update_member_role(request: Request, body: RoleUpdateRequest):
    """Promote or demote a team member."""
    workos_user_id = getattr(request.state, "user_id", None)
    if not workos_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    if body.new_role not in ("admin", "member"):
        raise HTTPException(status_code=400, detail="Invalid role. Must be 'admin' or 'member'")

    pool = get_pool()
    async with pool.acquire() as conn:
        req_info = await _get_requester_team_info(conn, workos_user_id)

        # ONLY Owners can assign Admin privileges
        if req_info["team_role"] != "owner":
            raise HTTPException(status_code=403, detail="Forbidden: Only Owners can manage roles")

        try:
            target_uuid = uuid.UUID(body.target_user_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid user ID format")

        target_row = await conn.fetchrow(
            """
            SELECT team_id, team_role FROM users WHERE id = $1
        """,
            target_uuid,
        )

        if not target_row or target_row["team_id"] != req_info["team_id"]:
            raise HTTPException(status_code=400, detail="Target user not found on your team")

        if target_row["team_role"] == "owner":
            raise HTTPException(status_code=400, detail="Cannot demote the team owner")

        await conn.execute(
            """
            UPDATE users SET team_role = $1 WHERE id = $2
        """,
            body.new_role,
            target_uuid,
        )

        return {"status": "success", "message": f"User role updated to {body.new_role}"}
