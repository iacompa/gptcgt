import asyncio
import os
import sys
from pathlib import Path

# Add the project root to the path so we can run this script directly
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    import asyncpg
except ImportError:
    print("Error: asyncpg is required. Run `pip install asyncpg`")
    sys.exit(1)

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgres://postgres:postgres@localhost:5432/gptcgt",  # Default fallback for local testing without DB  # noqa: E501
)


async def run_migration():
    migrations = [
        "001_initial_schema.sql",
        "002_billing_moderation.sql",
        "003_tos_tracking.sql",
        "004_api_key_hashes.sql",
    ]

    print("Connecting to database...")
    try:
        conn = await asyncpg.connect(DATABASE_URL)

        for migration in migrations:
            schema_path = Path(__file__).parent / migration
            if not schema_path.exists():
                print(f"Warning: Schema file not found at {schema_path}, skipping...")
                continue

            sql = schema_path.read_text()
            print(f"Applying schema {migration}...")
            await conn.execute(sql)

        print("All schemas applied successfully!")

    except Exception as e:
        print(f"Migration failed at {migration}: {e}")
    finally:
        if "conn" in locals():
            await conn.close()


if __name__ == "__main__":
    if not os.environ.get("DATABASE_URL"):
        print("WARNING: DATABASE_URL not set in environment. Using localhost fallback.")
    asyncio.run(run_migration())
