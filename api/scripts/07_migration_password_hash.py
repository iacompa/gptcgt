"""
Migration 07: Add password_hash column to users table.

Required for bcrypt password verification in auth hardening.
"""

import asyncio
import os

import asyncpg


async def run():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL not set, skipping migration")
        return

    conn = await asyncpg.connect(db_url)
    try:
        # Add password_hash column if it doesn't exist
        await conn.execute("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS password_hash TEXT DEFAULT NULL
        """)
        print("✅ Migration 07: Added password_hash column to users table")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run())
