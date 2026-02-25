import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Request

from api.database import get_pool

logger = logging.getLogger(__name__)
router = APIRouter(tags=["usage"])


@router.get("/")
async def get_usage(
    request: Request, start_date: Optional[str] = None, end_date: Optional[str] = None
):
    """Get usage events for the current user."""
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    pool = get_pool()
    internal_id = await pool.fetchval("SELECT id FROM users WHERE workos_user_id = $1", user_id)
    if not internal_id:
        raise HTTPException(status_code=404, detail="User not found")

    query = """
        SELECT id, task_mode, credits_consumed, models_used, input_tokens, output_tokens, created_at
        FROM usage_events
        WHERE user_id = $1
    """
    args = [internal_id]

    if start_date:
        query += " AND created_at >= $2"
        args.append(datetime.fromisoformat(start_date))
    if end_date:
        query += f" AND created_at <= ${len(args) + 1}"
        args.append(datetime.fromisoformat(end_date))

    query += " ORDER BY created_at DESC LIMIT 100"

    rows = await pool.fetch(query, *args)

    result = []
    for row in rows:
        result.append(
            {
                "id": row["id"],
                "task_mode": row["task_mode"],
                "credits_consumed": row["credits_consumed"],
                "models_used": row["models_used"],
                "input_tokens": row["input_tokens"],
                "output_tokens": row["output_tokens"],
                "created_at": row["created_at"].isoformat(),
            }
        )

    return result
