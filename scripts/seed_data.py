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
from app.core.timeutils import local_now
from app.models.carrier_group import CarrierGroup
from app.models.carrier_type import CarrierType
from app.models.holiday import Holiday
from app.models.role import Role
from app.models.user import User
from app.services.holiday_service import HolidayService

# Make variables from the .env file visible to os.getenv (shell vars still win).
load_dotenv()

# Descriptions are shown in the admin UI, hence Polish.
ROLES = [
    ("admin", "Pełny dostęp, także konfiguracja"),
    ("manager", "Wszystkie operacje i audyt, bez konfiguracji"),
    ("controller", "Przeksięgowania i inwentaryzacja"),
    ("operator", "Operacje magazynowe"),
    ("viewer", "Tylko podgląd"),
]

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

# Starting dictionaries (names as given by the manager); the admin edits them later.
# group -> [(type, counted in reports)], in the order shown in lists.
CARRIERS = {
    "EUR": [
        ("EURO", True),
        ("EURO uszkodzone", False),
        ("EURO utylizacja", False),
    ],
    "Jednorazowe": [("Jednorazowe", True)],
}


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

    if await _is_empty(session, CarrierGroup):
        for group_name, types in CARRIERS.items():
            group = CarrierGroup(name=group_name)
            session.add(group)
            await session.flush()
            session.add_all(
                CarrierType(
                    group_uuid=group.uuid,
                    name=name,
                    sort_order=order,
                    count_in_reports=counted,
                )
                for order, (name, counted) in enumerate(types, start=1)
            )
        filled.append("carrier groups and types")

    await session.flush()
    return filled


async def seed_holidays(session: AsyncSession) -> list[int]:
    """Fill this year's and next year's Polish public holidays while the list is
    empty; a day the admin removed later is not brought back. Returns the years
    filled."""
    if not await _is_empty(session, Holiday):
        return []
    year = local_now().year
    service = HolidayService(session)
    for each in (year, year + 1):
        await service.add_public(None, each)
    return [year, year + 1]


async def seed_first_admin(
    session: AsyncSession, admin_role: Role, username: str, password: str | None
) -> tuple[str, str | None]:
    """Create the first admin, but only while the system has no admin at all.

    Checking by username instead would create a second full-access account on the
    next start after the admin renamed theirs.
    Returns (status, generated password or None); status is "exists",
    "username-taken" or "created".
    """
    admins = await session.execute(
        select(func.count()).select_from(User).where(User.role_uuid == admin_role.uuid)
    )
    if admins.scalar_one() > 0:
        return "exists", None

    taken = await session.execute(select(User).where(User.username == username))
    if taken.scalar_one_or_none() is not None:
        return "username-taken", None

    generated = None if password else secrets.token_urlsafe(12)
    session.add(
        User(
            username=username,
            hashed_password=hash_password(password or generated),
            role_uuid=admin_role.uuid,
            is_active=True,
        )
    )
    await session.flush()
    return "created", generated


async def seed_roles(session: AsyncSession) -> dict[str, Role]:
    """Add the missing roles. Descriptions belong to the code, so an existing
    role gets the current one."""
    roles: dict[str, Role] = {}
    for name, description in ROLES:
        role = (
            await session.execute(select(Role).where(Role.name == name))
        ).scalar_one_or_none()
        if role is None:
            role = Role(name=name, description=description)
            session.add(role)
        else:
            role.description = description
        roles[name] = role
    await session.flush()
    return roles


async def seed() -> None:
    async with AsyncSessionLocal() as session:
        roles = await seed_roles(session)

        status, generated = await seed_first_admin(
            session, roles["admin"], ADMIN_USERNAME, ADMIN_PASSWORD
        )
        if status == "exists":
            print("An admin user already exists.")
        elif status == "username-taken":
            print(
                f"No admin exists, but the username '{ADMIN_USERNAME}' is taken by a"
                " non-admin user; set ADMIN_USERNAME to a free one."
            )
        elif generated:
            print(f"Created admin user '{ADMIN_USERNAME}' with a generated password:")
            print(f"    {generated}")
            print("Save it now - it will NOT be shown again.")
        else:
            print(f"Created admin user '{ADMIN_USERNAME}'.")

        years = await seed_holidays(session)
        if years:
            print("Filled the public holidays of " + ", ".join(map(str, years)) + ".")

        filled = await seed_dictionaries(session)
        if filled:
            print("Filled the starting " + ", ".join(filled) + ".")
        else:
            print("Dictionaries already have data, left unchanged.")

        await session.commit()

    print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(seed())
