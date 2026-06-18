import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def check():
    engine = create_async_engine("sqlite+aiosqlite:///./feedback_platform.db")
    async with engine.connect() as conn:
        rows = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        tables = [r[0] for r in rows]
        print("Tables:", tables)
        if "users" in tables:
            count = (await conn.execute(text("SELECT COUNT(*) FROM users"))).scalar()
            print("User count:", count)
            if count:
                rows = await conn.execute(text("SELECT id, email, role, hashed_password FROM users"))
                for r in rows:
                    print(f"  {r[1]} | {r[2]} | hash={r[3][:30]}...")
        if "organizations" in tables:
            count = (await conn.execute(text("SELECT COUNT(*) FROM organizations"))).scalar()
            print("Org count:", count)
    await engine.dispose()

asyncio.run(check())
