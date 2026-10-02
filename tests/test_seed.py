from sqlalchemy import select

from app.models.area import Area
from app.models.pallet_type import PalletType
from app.models.quality import Quality
from scripts.seed_data import AREAS, seed_dictionaries


async def names(session, model, order):
    return (await session.execute(select(model.name).order_by(order))).scalars().all()


async def test_fills_empty_dictionaries(session):
    filled = await seed_dictionaries(session)
    await session.commit()

    assert filled == ["areas", "pallet types", "qualities"]
    assert sorted(await names(session, Area, Area.name)) == sorted(AREAS)
    assert await names(session, PalletType, PalletType.name) == ["EUR"]
    assert await names(session, Quality, Quality.sort_order) == ["I", "II", "III"]


async def test_running_again_adds_nothing(session):
    await seed_dictionaries(session)
    await session.commit()

    filled = await seed_dictionaries(session)

    assert filled == []
    assert len(await names(session, Area, Area.name)) == len(AREAS)


async def test_does_not_bring_back_what_the_admin_renamed(session):
    await seed_dictionaries(session)
    area = (
        await session.execute(select(Area).where(Area.name == "Zwrot 445"))
    ).scalar_one()
    area.name = "Zwroty 445"
    await session.commit()

    await seed_dictionaries(session)
    await session.commit()

    current = await names(session, Area, Area.name)
    assert "Zwrot 445" not in current
    assert "Zwroty 445" in current
