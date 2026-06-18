import asyncio
import sys
sys.path.insert(0, ".")

from httpx import AsyncClient, ASGITransport
from app.main import app

async def test():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/v1/auth/login", json={"email": "admin@bilvantis.io", "password": "Admin@1234"})
        print(f"Status: {r.status_code}")
        print(f"Body: {r.text}")

asyncio.run(test())
