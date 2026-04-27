import asyncio
import os
import asyncpg
from dotenv import load_dotenv

async def init_db():
    load_dotenv()
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL not found in .env")
        return

    print(f"Connecting to {db_url.split('@')[-1]}...")
    conn = await asyncpg.connect(db_url)
    try:
        with open("schema.sql", "r") as f:
            schema_sql = f.read()
        
        print("Applying schema...")
        await conn.execute(schema_sql)
        print("Schema applied successfully!")
    except Exception as e:
        print(f"Error applying schema: {e}")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(init_db())
