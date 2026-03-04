"""Migration: Add GitHub integration columns to users table."""

import asyncio
import os

import asyncpg


async def run_migration():
    """Add github_token and github_username columns."""
    dsn = os.getenv("DATABASE_URL", "postgresql://localhost:5432/gptcgt")
    conn = await asyncpg.connect(dsn)

    try:
        await conn.execute("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS github_token TEXT,
            ADD COLUMN IF NOT EXISTS github_username TEXT;
        """)
        print("✅ GitHub columns added to users table")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run_migration())
