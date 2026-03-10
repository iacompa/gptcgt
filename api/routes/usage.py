import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Request

from api.database import get_pool

logger = logging.getLogger(__name__)
router = APIRouter(tags=["usage"])
DEFAULT_RECENT_LIMIT = 100
RANGED_LIMIT = 5000
MAX_LIMIT = 5000


def _parse_iso_datetime(value: Optional[str], field_name: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid {field_name}; expected ISO 8601 datetime") from exc


@router.get("/")
async def get_usage(
    request: Request,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: Optional[int] = None,
):
    """Get usage events for the current user from the immutable usage_events table."""
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    parsed_start = _parse_iso_datetime(start_date, "start_date")
    parsed_end = _parse_iso_datetime(end_date, "end_date")
    if parsed_start and parsed_end and parsed_start > parsed_end:
        raise HTTPException(status_code=400, detail="start_date must be before end_date")

    effective_limit = limit
    if effective_limit is None:
        effective_limit = RANGED_LIMIT if (parsed_start or parsed_end) else DEFAULT_RECENT_LIMIT
    if effective_limit < 1 or effective_limit > MAX_LIMIT:
        raise HTTPException(status_code=400, detail=f"limit must be between 1 and {MAX_LIMIT}")

    pool = get_pool()
    internal_id = await pool.fetchval("SELECT id FROM users WHERE workos_user_id = $1", user_id)
    if not internal_id:
        raise HTTPException(status_code=404, detail="User not found")

    query = """
        SELECT id, task_mode, credits_consumed, models_used, input_tokens, output_tokens,
               created_at
        FROM usage_events
        WHERE user_id = $1
    """
    args = [internal_id]

    if parsed_start:
        args.append(parsed_start)
        query += f" AND created_at >= ${len(args)}"
    if parsed_end:
        args.append(parsed_end)
        query += f" AND created_at <= ${len(args)}"

    args.append(effective_limit)
    query += f" ORDER BY created_at DESC LIMIT ${len(args)}"

    try:
        rows = await pool.fetch(query, *args)
    except Exception as e:
        logger.error(f"Usage query failed: {e}", exc_info=True)
        raise HTTPException(status_code=502, detail=f"Usage query failed: {type(e).__name__}")

    result = []
    for row in rows:
        result.append(
            {
                "id": str(row["id"]),
                "task_mode": row["task_mode"],
                "credits_consumed": row["credits_consumed"],
                "models_used": row["models_used"] or [],
                "input_tokens": row["input_tokens"] or 0,
                "output_tokens": row["output_tokens"] or 0,
                "created_at": row["created_at"].isoformat(),
            }
        )

    return result
