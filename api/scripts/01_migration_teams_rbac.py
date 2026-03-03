import asyncio
import os
import sys

# Add the project root to the python path so imports work
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging

from api.database import close_db_pool, get_pool, init_db_pool

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("migration")

async def run_migration():
    await init_db_pool()
    pool = get_pool()

    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                logger.info("Starting Enterprise RBAC and Usage Log Migration...")

                # 1. Create the Teams table
                logger.info("Creating 'teams' table...")
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS teams (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        name VARCHAR(255) NOT NULL,
                        stripe_customer_id VARCHAR(255) UNIQUE,
                        plan VARCHAR(50) DEFAULT 'free',
                        shared_credits_remaining INT DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)

                # 2. Add RBAC & Quota columns to users
                logger.info("Altering 'users' table to support RBAC and Teams...")
                await conn.execute("""
                    ALTER TABLE users
                        ADD COLUMN IF NOT EXISTS team_id UUID REFERENCES teams(id),
                        ADD COLUMN IF NOT EXISTS team_role VARCHAR(50) DEFAULT 'owner',
                        ADD COLUMN IF NOT EXISTS allocated_quota INT,
                        ADD COLUMN IF NOT EXISTS billing_access BOOLEAN DEFAULT TRUE;
                """)

                # 3. Create the Usage Logs table for Stripe audit trails
                logger.info("Creating 'usage_logs' table for Token/Credit tracking...")
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS usage_logs (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        team_id UUID REFERENCES teams(id),
                        user_id INTEGER REFERENCES users(id),
                        action VARCHAR(255) NOT NULL,
                        tokens_used INT NOT NULL,
                        stripe_invoice_id VARCHAR(255),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)

                # 4. Add moderation columns to users
                logger.info("Adding moderation columns to 'users' table...")
                await conn.execute("""
                    ALTER TABLE users
                        ADD COLUMN IF NOT EXISTS suspended_at TIMESTAMP,
                        ADD COLUMN IF NOT EXISTS suspended_until TIMESTAMP,
                        ADD COLUMN IF NOT EXISTS suspended_reason TEXT;
                """)

                # 5. Create the audit_log table for moderation tracking
                logger.info("Creating 'audit_log' table...")
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS audit_log (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER REFERENCES users(id),
                        action VARCHAR(255) NOT NULL,
                        details JSONB,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)

                # 6. Create the api_keys table if it doesn't exist
                logger.info("Ensuring 'api_keys' table exists...")
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS api_keys (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        owner_type VARCHAR(50) NOT NULL DEFAULT 'user',
                        owner_id INTEGER REFERENCES users(id),
                        provider VARCHAR(100) NOT NULL,
                        encrypted_key BYTEA NOT NULL,
                        key_hash VARCHAR(255) NOT NULL,
                        is_active BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)

                # 7. Data Migration: Create a 1-to-1 Team for every existing user so they don't break
                logger.info("Migrating existing individual users into individual Teams...")
                existing_users = await conn.fetch(
                    "SELECT id, email, stripe_customer_id, plan, "
                    "credits_remaining FROM users WHERE team_id IS NULL"
                )

                for user in existing_users:
                    # Parse out a company/team name from the email (e.g. michael@example.com -> 'example')
                    domain = user["email"].split("@")[-1].split(".")[0].capitalize()
                    team_name = f"{domain} Workspace"

                    # Create the Team, transfer their stripe info and remaining credits into the pooling wallet
                    team_id = await conn.fetchval("""
                        INSERT INTO teams (name, stripe_customer_id, plan, shared_credits_remaining)
                        VALUES ($1, $2, $3, $4)
                        RETURNING id
                    """, team_name, user["stripe_customer_id"], user["plan"], user["credits_remaining"] or 0)

                    # Link the user backwards to the Team as the Owner
                    await conn.execute("""
                        UPDATE users
                        SET team_id = $1, team_role = 'owner', billing_access = TRUE
                        WHERE id = $2
                    """, team_id, user["id"])

                logger.info(f"Successfully migrated {len(existing_users)} standalone users into RBAC Workspaces.")

    except Exception as e:
        logger.error(f"Migration Failed: {e}")
        raise e
    finally:
        await close_db_pool()

if __name__ == "__main__":
    asyncio.run(run_migration())
