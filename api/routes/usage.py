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
    """Get usage events for the current user from the immutable usage_logs table."""
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    pool = get_pool()
    internal_id = await pool.fetchval("SELECT id FROM users WHERE workos_user_id = $1", user_id)
    if not internal_id:
        raise HTTPException(status_code=404, detail="User not found")

    query = """
        SELECT id, action as task_mode, tokens_used as credits_consumed,
               '{}' as models_used, tokens_used as input_tokens, 0 as output_tokens,
               created_at
        FROM usage_logs
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

    try:
        rows = await pool.fetch(query, *args)
    except Exception as e:
        logger.warning(f"Usage query failed (table may not exist yet): {e}")
        return []

    result = []
    for row in rows:
        result.append(
            {
                "id": str(row["id"]),
                "task_mode": row["task_mode"],
                "credits_consumed": row["credits_consumed"],
                "models_used": [row["task_mode"].split("(")[-1].rstrip(")")] if "(" in row["task_mode"] else [],
                "input_tokens": row["input_tokens"],
                "output_tokens": row["output_tokens"],
                "created_at": row["created_at"].isoformat(),
            }
        )

    return result
