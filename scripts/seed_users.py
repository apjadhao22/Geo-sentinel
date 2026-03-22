import asyncio
from app.database import async_session_factory
from app.models.user import User
from app.services.auth_service import hash_password


async def seed():
    async with async_session_factory() as db:
        users = [
            User(username="superadmin", password_hash=hash_password("admin123"), full_name="PCMC Super Admin", role="super_admin"),
            User(username="admin1", password_hash=hash_password("admin123"), full_name="PCMC Admin", role="admin"),
            User(username="reviewer1", password_hash=hash_password("review123"), full_name="Field Officer 1", role="reviewer"),
            User(username="reviewer2", password_hash=hash_password("review123"), full_name="Field Officer 2", role="reviewer"),
        ]
        for u in users:
            db.add(u)
        await db.commit()
        print(f"Seeded {len(users)} users")


if __name__ == "__main__":
    asyncio.run(seed())
