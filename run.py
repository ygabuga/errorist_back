import asyncio
import uvicorn
from app.database import init_db

async def main():
    await init_db()
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)

if __name__ == "__main__":
    asyncio.run(main())