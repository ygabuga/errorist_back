import asyncio
import asyncpg

# ЗАМЕНИТЕ ПАРОЛЬ!
DATABASE_URL = "postgresql+asyncpg://postgres:admin@localhost:5432/atm_db"

async def test():
    try:
        conn = await asyncpg.connect(
            user="postgres",
            password="ваш_пароль",  # ← сюда ваш пароль
            database="atm_db",
            host="localhost",
            port=5432
        )
        version = await conn.fetchval("SELECT version()")
        print(f"✅ Подключено! PostgreSQL: {version[:50]}...")
        await conn.close()
    except Exception as e:
        print(f"❌ Ошибка: {e}")

asyncio.run(test())