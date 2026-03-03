import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def main():
    conn = await asyncpg.connect(os.environ.get("DATABASE_URL"))
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            workos_user_id VARCHAR(255) UNIQUE NOT NULL,
            email VARCHAR(255) NOT NULL,
            stripe_customer_id VARCHAR(255),
            plan VARCHAR(50) DEFAULT 'free',
            credits_remaining INTEGER DEFAULT 0,
            credits_monthly INTEGER DEFAULT 0,
            spending_cap INTEGER DEFAULT 0,
            overage_enabled BOOLEAN DEFAULT false,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE
        );
        CREATE TABLE IF NOT EXISTS events (
            id SERIAL PRIMARY KEY,
            workos_user_id VARCHAR(255) NOT NULL,
            event_type VARCHAR(100) NOT NULL,
            metadata JSONB,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
    """)
    print("Tables created successfully!")
    await conn.close()

asyncio.run(main())
