import asyncio
import sys
sys.path.insert(0, ".")

from app.core.seed import seed_database

async def main():
    try:
        await seed_database()
        print("Seed complete")
    except Exception as e:
        print(f"Seed ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

asyncio.run(main())
