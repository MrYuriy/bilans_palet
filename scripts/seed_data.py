"""Seed roles and an initial admin user.

Usage:
    ADMIN_PASSWORD=... python -m scripts.seed_data   # use a chosen password
    python -m scripts.seed_data                       # password is generated and printed once

The admin password is never hardcoded: it comes from the ADMIN_PASSWORD env var,
otherwise a strong one is generated and shown a single time.
Idempotent: re-running will not create duplicates.
"""

import asyncio
import os
import secrets

from dotenv import load_dotenv
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models.role import Role
from app.models.user import User

# Make variables from the .env file visible to os.getenv (shell vars still win).
load_dotenv()

# Descriptions are shown in the admin UI, hence Polish.
ROLES = [
    ("admin", "Pełny dostęp"),
    ("operator", "Wprowadzanie ruchów i inwentaryzacji"),
    ("viewer", "Tylko podgląd"),
]

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")


async def seed() -> None:
    async with AsyncSessionLocal() as session:
        roles: dict[str, Role] = {}

        for name, description in ROLES:
            role = (
                await session.execute(select(Role).where(Role.name == name))
            ).scalar_one_or_none()

            if role is None:
                role = Role(name=name, description=description)
                session.add(role)
                await session.flush()

            roles[name] = role

        admin = (
            await session.execute(select(User).where(User.username == ADMIN_USERNAME))
        ).scalar_one_or_none()

        if admin is None:
            password = ADMIN_PASSWORD or secrets.token_urlsafe(12)
            session.add(
                User(
                    username=ADMIN_USERNAME,
                    hashed_password=hash_password(password),
                    role_uuid=roles["admin"].uuid,
                    is_active=True,
                )
            )
            if ADMIN_PASSWORD:
                print(f"Created admin user '{ADMIN_USERNAME}'.")
            else:
                print(
                    f"Created admin user '{ADMIN_USERNAME}' with a generated password:"
                )
                print(f"    {password}")
                print("Save it now - it will NOT be shown again.")
        else:
            print(f"Admin user '{ADMIN_USERNAME}' already exists.")

        await session.commit()

    print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(seed())
