from sqlalchemy import select

from app.core.security import verify_password
from app.models.carrier_group import CarrierGroup
from app.models.carrier_type import CarrierType
from app.models.role import Role
from app.models.user import User
from scripts.seed_data import seed_dictionaries, seed_first_admin
from tests.conftest import make_user


async def admin_role(session) -> Role:
    role = Role(name="admin")
    session.add(role)
    await session.flush()
    return role


async def usernames(session):
    return (await session.execute(select(User.username))).scalars().all()


async def test_creates_the_first_admin_with_the_given_password(session):
    role = await admin_role(session)

    status, generated = await seed_first_admin(session, role, "admin", "Haslo1!")

    assert (status, generated) == ("created", None)
    user = (await session.execute(select(User))).scalar_one()
    assert user.username == "admin"
    assert user.role_uuid == role.uuid
    assert verify_password("Haslo1!", user.hashed_password)


async def test_generates_a_password_when_none_is_given(session):
    role = await admin_role(session)

    status, generated = await seed_first_admin(session, role, "admin", None)

    user = (await session.execute(select(User))).scalar_one()
    assert status == "created"
    assert generated
    assert verify_password(generated, user.hashed_password)


async def test_no_second_admin_after_the_admin_renamed_themselves(session):
    role = await admin_role(session)
    await seed_first_admin(session, role, "admin", "Haslo1!")
    user = (await session.execute(select(User))).scalar_one()
    user.username = "anna.nowak"
    await session.flush()

    status, _ = await seed_first_admin(session, role, "admin", "Haslo1!")

    assert status == "exists"
    assert await usernames(session) == ["anna.nowak"]


async def test_username_taken_by_a_non_admin(session):
    role = await admin_role(session)
    await make_user(session, "admin", role="operator")

    status, _ = await seed_first_admin(session, role, "admin", "Haslo1!")

    assert status == "username-taken"
    assert await usernames(session) == ["admin"]


async def names(session, model, order):
    return (await session.execute(select(model.name).order_by(order))).scalars().all()


async def test_fills_empty_dictionaries(session):
    filled = await seed_dictionaries(session)
    await session.commit()

    assert filled == ["carrier groups and types"]
    assert await names(session, CarrierGroup, CarrierGroup.name) == [
        "EUR",
        "Jednorazowe",
    ]
    types = (await session.execute(select(CarrierType))).scalars().all()
    assert {(t.name, t.count_in_reports) for t in types} == {
        ("EURO", True),
        ("EURO uszkodzone", False),
        ("EURO utylizacja", False),
        ("Jednorazowe", True),
    }


async def test_running_again_adds_nothing(session):
    await seed_dictionaries(session)
    await session.commit()

    filled = await seed_dictionaries(session)

    assert filled == []
    assert len(await names(session, CarrierType, CarrierType.name)) == 4


async def test_does_not_bring_back_what_the_admin_renamed(session):
    await seed_dictionaries(session)
    damaged = (
        await session.execute(
            select(CarrierType).where(CarrierType.name == "EURO uszkodzone")
        )
    ).scalar_one()
    damaged.name = "EURO do naprawy"
    await session.commit()

    await seed_dictionaries(session)
    await session.commit()

    current = await names(session, CarrierType, CarrierType.name)
    assert "EURO uszkodzone" not in current
    assert "EURO do naprawy" in current
