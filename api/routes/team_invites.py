"""Team invitation, member management, and team lifecycle routes."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr

from api.database import get_pool

router = APIRouter(tags=["team_invites"])


class InviteRequest(BaseModel):
    """Invite a new member by email."""

    email: EmailStr
    role: str = "member"  # "member" or "admin"


class AcceptInviteRequest(BaseModel):
    """Accept a pending invite."""

    invite_id: str


class RemoveMemberRequest(BaseModel):
    """Remove a member from the team."""

    target_user_id: str


# ------------------------------------------------------------------ #
#  Invite flow                                                        #
# ------------------------------------------------------------------ #


@router.post("/invite")
async def invite_member(request: Request, body: InviteRequest):
    """Owner or admin invites a new member by email."""
    workos_user_id = getattr(request.state, "user_id", None)
    if not workos_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    if body.role not in ("member", "admin"):
        raise HTTPException(status_code=400, detail="Role must be 'member' or 'admin'")

    pool = get_pool()
    async with pool.acquire() as conn:
        # Verify requester is owner or admin
        req = await conn.fetchrow(
            "SELECT team_id, team_role FROM users WHERE workos_user_id = $1",
            workos_user_id,
        )
        if not req or req["team_role"] not in ("owner", "admin"):
            raise HTTPException(status_code=403, detail="Only owners and admins can invite")

        # Check if email is already on the team
        existing = await conn.fetchrow(
            "SELECT id FROM users WHERE email = $1 AND team_id = $2",
            body.email,
            req["team_id"],
        )
        if existing:
            raise HTTPException(status_code=409, detail="User is already on your team")

        # Check for duplicate pending invite
        dup = await conn.fetchval(
            """
            SELECT 1 FROM team_invites
            WHERE email = $1 AND team_id = $2 AND status = 'pending'
            """,
            body.email,
            req["team_id"],
        )
        if dup:
            raise HTTPException(status_code=409, detail="Invite already pending for this email")

        # Create the invite
        invite_id = str(uuid.uuid4())
        await conn.execute(
            """
            INSERT INTO team_invites (id, team_id, email, role, invited_by, status, created_at)
            VALUES ($1, $2, $3, $4, $5, 'pending', $6)
            """,
            uuid.UUID(invite_id),
            req["team_id"],
            body.email,
            body.role,
            workos_user_id,
            datetime.now(timezone.utc),
        )

    return {"status": "invited", "invite_id": invite_id, "email": body.email}


@router.post("/accept")
async def accept_invite(request: Request, body: AcceptInviteRequest):
    """Accept a pending team invite. Caller must be authenticated."""
    workos_user_id = getattr(request.state, "user_id", None)
    if not workos_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    pool = get_pool()
    async with pool.acquire() as conn:
        try:
            invite_uuid = uuid.UUID(body.invite_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid invite ID format")

        # Find the invite
        invite = await conn.fetchrow(
            """
            SELECT id, team_id, email, role, status
            FROM team_invites WHERE id = $1
            """,
            invite_uuid,
        )
        if not invite:
            raise HTTPException(status_code=404, detail="Invite not found")
        if invite["status"] != "pending":
            raise HTTPException(status_code=400, detail=f"Invite is {invite['status']}")

        # Verify the accepting user's email matches the invite
        user = await conn.fetchrow(
            "SELECT id, email, team_id FROM users WHERE workos_user_id = $1",
            workos_user_id,
        )
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        if user["email"] != invite["email"]:
            raise HTTPException(
                status_code=403,
                detail="This invite was sent to a different email",
            )

        # Move user to the new team
        await conn.execute(
            """
            UPDATE users
            SET team_id = $1, team_role = $2
            WHERE workos_user_id = $3
            """,
            invite["team_id"],
            invite["role"],
            workos_user_id,
        )

        # Mark invite as accepted
        await conn.execute(
            "UPDATE team_invites SET status = 'accepted' WHERE id = $1",
            invite["id"],
        )

    return {"status": "accepted", "team_id": str(invite["team_id"])}


@router.get("/pending")
async def list_pending_invites(request: Request):
    """List pending invites for the caller's team (owner/admin only)."""
    workos_user_id = getattr(request.state, "user_id", None)
    if not workos_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    pool = get_pool()
    async with pool.acquire() as conn:
        req = await conn.fetchrow(
            "SELECT team_id, team_role FROM users WHERE workos_user_id = $1",
            workos_user_id,
        )
        if not req or req["team_role"] not in ("owner", "admin"):
            raise HTTPException(status_code=403, detail="Forbidden")

        rows = await conn.fetch(
            """
            SELECT id, email, role, status, created_at
            FROM team_invites
            WHERE team_id = $1 AND status = 'pending'
            ORDER BY created_at DESC
            """,
            req["team_id"],
        )

    return [
        {
            "id": str(r["id"]),
            "email": r["email"],
            "role": r["role"],
            "created_at": r["created_at"].isoformat(),
        }
        for r in rows
    ]


# ------------------------------------------------------------------ #
#  Member removal                                                      #
# ------------------------------------------------------------------ #


@router.delete("/member")
async def remove_member(request: Request, body: RemoveMemberRequest):
    """Remove a member from the team. Owner/admin only. Cannot remove owner."""
    workos_user_id = getattr(request.state, "user_id", None)
    if not workos_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    pool = get_pool()
    async with pool.acquire() as conn:
        req = await conn.fetchrow(
            "SELECT team_id, team_role FROM users WHERE workos_user_id = $1",
            workos_user_id,
        )
        if not req or req["team_role"] not in ("owner", "admin"):
            raise HTTPException(status_code=403, detail="Only owners/admins can remove members")

        try:
            target_uuid = uuid.UUID(body.target_user_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid user ID format")

        target = await conn.fetchrow(
            "SELECT id, team_id, team_role FROM users WHERE id = $1",
            target_uuid,
        )
        if not target or target["team_id"] != req["team_id"]:
            raise HTTPException(status_code=404, detail="User not on your team")
        if target["team_role"] == "owner":
            raise HTTPException(status_code=400, detail="Cannot remove the team owner")
        if req["team_role"] == "admin" and target["team_role"] == "admin":
            raise HTTPException(status_code=403, detail="Admins cannot remove other admins")

        # Create a personal team for the removed user
        personal_team_id = await conn.fetchval(
            """
            INSERT INTO teams (name, plan, shared_credits_remaining)
            VALUES ('Personal Workspace', 'free', 0)
            RETURNING id
            """,
        )

        # Move user to their personal team
        await conn.execute(
            """
            UPDATE users
            SET team_id = $1, team_role = 'owner'
            WHERE id = $2
            """,
            personal_team_id,
            target["id"],
        )

    return {"status": "removed", "user_id": body.target_user_id}


# ------------------------------------------------------------------ #
#  Team lifecycle                                                      #
# ------------------------------------------------------------------ #


@router.delete("/")
async def delete_team(request: Request):
    """Delete the team. Owner only. All members get personal workspaces."""
    workos_user_id = getattr(request.state, "user_id", None)
    if not workos_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            req = await conn.fetchrow(
                "SELECT id, team_id, team_role, stripe_subscription_id FROM users WHERE workos_user_id = $1",
                workos_user_id,
            )
            if not req or req["team_role"] != "owner":
                raise HTTPException(status_code=403, detail="Only the owner can delete the team")

            team_id = req["team_id"]

            # L3: Cancel Stripe subscription if active.
            stripe_sub_id = req["stripe_subscription_id"]
            if stripe_sub_id:
                try:
                    import logging

                    import stripe

                    from api.config import settings

                    stripe.api_key = settings.stripe_secret_key
                    stripe.Subscription.delete(stripe_sub_id)
                except Exception as e:
                    logging.getLogger(__name__).error(
                        f"Failed to cancel Stripe subscription {stripe_sub_id}: {e}"
                    )

            # Downgrade owner to free plan before moving everyone to personal workspaces.
            await conn.execute(
                "UPDATE users SET plan = 'free', credits_monthly = 0, subscription_status = 'cancelled', stripe_subscription_id = NULL WHERE id = $1",
                req["id"],
            )

            members = await conn.fetch(
                "SELECT id FROM users WHERE team_id = $1 AND id != $2",
                team_id,
                req["id"],
            )

            for member in members:
                personal_id = await conn.fetchval(
                    """
                    INSERT INTO teams (name, plan, shared_credits_remaining)
                    VALUES ('Personal Workspace', 'free', 0)
                    RETURNING id
                    """,
                )
                await conn.execute(
                    "UPDATE users SET team_id = $1, team_role = 'owner' WHERE id = $2",
                    personal_id,
                    member["id"],
                )

            owner_team_id = await conn.fetchval(
                """
                INSERT INTO teams (name, plan, shared_credits_remaining)
                VALUES ('Personal Workspace', 'free', 0)
                RETURNING id
                """,
            )
            await conn.execute(
                "UPDATE users SET team_id = $1 WHERE id = $2",
                owner_team_id,
                req["id"],
            )

            await conn.execute(
                "UPDATE team_invites SET status = 'cancelled' WHERE team_id = $1 AND status = 'pending'",
                team_id,
            )

            await conn.execute("DELETE FROM teams WHERE id = $1", team_id)

    return {"status": "deleted"}


class RenameTeamRequest(BaseModel):
    name: str

@router.patch("/name")
async def rename_team(request: Request, body: RenameTeamRequest):
    """Rename the team. Owner only."""
    workos_user_id = getattr(request.state, "user_id", None)
    if not workos_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    new_name = body.name.strip()
    if not new_name or len(new_name) > 100:
        raise HTTPException(status_code=400, detail="Name must be 1-100 characters")

    pool = get_pool()
    async with pool.acquire() as conn:
        req = await conn.fetchrow(
            "SELECT team_id, team_role FROM users WHERE workos_user_id = $1",
            workos_user_id,
        )
        if not req or req["team_role"] != "owner":
            raise HTTPException(status_code=403, detail="Only the owner can rename the team")

        await conn.execute(
            "UPDATE teams SET name = $1 WHERE id = $2",
            new_name,
            req["team_id"],
        )

    return {"status": "renamed", "name": new_name}
