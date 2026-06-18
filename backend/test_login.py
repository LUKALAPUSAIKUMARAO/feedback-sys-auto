import asyncio
import sys
sys.path.insert(0, ".")

from app.core.database import AsyncSessionLocal
from app.models.db_models import User
from app.core.security import verify_password
from sqlalchemy import select

async def test():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == "admin@bilvantis.io"))
        user = result.scalar_one_or_none()
        if not user:
            print("ERROR: User not found")
            return
        print(f"User found: {user.email}, role={user.role}")
        print(f"Hash: {user.hashed_password[:30]}...")
        ok = verify_password("Admin@1234", user.hashed_password)
        print(f"Password valid: {ok}")

asyncio.run(test())
