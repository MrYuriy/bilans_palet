"""Seed roles, an initial admin user and the starting dictionaries.

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
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models.area import Area
from app.models.pallet_type import PalletType
from app.models.quality import Quality
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

# Starting dictionaries (names as given by the manager); the admin edits them later.
AREAS = [
    "Przyjęcia 445",
    "Przyjęcia Ecom",
    "Zwrot 445",
    "Zwroty Ecom",
    "Wysyłka 445",
    "Wysyłka Ecom",
    "Inwentaryzacja",
]
PALLET_TYPES = ["EUR"]
QUALITIES = [("I", 1), ("II", 2), ("III", 3)]


async def _is_empty(session: AsyncSession, model) -> bool:
    count = await session.execute(select(func.count()).select_from(model))
    return count.scalar_one() == 0


async def seed_dictionaries(session: AsyncSession) -> list[str]:
    """Fill each dictionary only while it is still empty.

    Seeding by name would bring back a row the admin renamed or deleted on the
    next start, so a dictionary that already has rows is left alone.
    Returns the names of the dictionaries that were filled.
    """
    filled = []

    if await _is_empty(session, Area):
        session.add_all(Area(name=name) for name in AREAS)
        filled.append("areas")

    if await _is_empty(session, PalletType):
        session.add_all(PalletType(name=name) for name in PALLET_TYPES)
        filled.append("pallet types")

    if await _is_empty(session, Quality):
        session.add_all(Quality(name=n, sort_order=o) for n, o in QUALITIES)
        filled.append("qualities")

    await session.flush()
    return filled


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

        filled = await seed_dictionaries(session)
        if filled:
            print("Filled the starting " + ", ".join(filled) + ".")
        else:
            print("Dictionaries already have data, left unchanged.")

        await session.commit()

    print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(seed())
