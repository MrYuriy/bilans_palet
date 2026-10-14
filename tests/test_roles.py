"""Who may do what. The rights are provisional (PermissionService), so these
tests pin down the table as it stands."""

import pytest

from app.models.role import Role
from scripts.seed_data import ROLES, seed_roles
from tests.conftest import line, login, make_user, move

ENTERS = {
    # role: (everyday operations, re-classification, stock count)
    "admin": (True, True, True),
    "manager": (True, True, True),
    "controller": (False, True, True),
    "operator": (True, False, False),
    "viewer": (False, False, False),
}


async def headers_of(client, session, role):
    await make_user(session, "jan", role=role)
    return await login(client, "jan")


def status(allowed: bool) -> int:
    return 200 if allowed else 403


@pytest.mark.parametrize("role", list(ENTERS))
async def test_what_each_role_enters(client, session, carriers, role):
    operations, reclassification, counting = ENTERS[role]
    headers = await headers_of(client, session, role)

    transfer = await move(client, headers, "ECOM_TRANSFER", line(carriers.euro, 1))
    correction = await move(client, headers, "CORRECTION", line(carriers.euro, 1))
    reclass = await move(
        client, headers, "RECLASSIFICATION", line(carriers.euro, 1, to=carriers.damaged)
    )
    sheet = await client.get("/inventories/sheet", headers=headers)
    count = await client.post(
        "/inventories",
        headers=headers,
        json={"lines": [{"carrier_type_uuid": carriers.euro, "counted_quantity": 3}]},
    )

    assert (transfer.status_code, correction.status_code) == (status(operations),) * 2
    assert reclass.status_code == status(reclassification)
    assert (sheet.status_code, count.status_code) == (status(counting),) * 2


@pytest.mark.parametrize("role", list(ENTERS))
async def test_everyone_reads_the_stock(client, session, carriers, role):
    headers = await headers_of(client, session, role)

    for url in ("/balances/current", "/balances/daily", "/movements"):
        assert (await client.get(url, headers=headers)).status_code == 200


@pytest.mark.parametrize(
    ("role", "configures", "audits"),
    [
        ("admin", True, True),
        ("manager", False, True),
        ("controller", False, False),
        ("operator", False, False),
        ("viewer", False, False),
    ],
)
async def test_only_the_admin_configures(client, session, role, configures, audits):
    headers = await headers_of(client, session, role)

    settings = await client.put(
        "/settings", headers=headers, json={"day_cutoff": "00:00"}
    )
    group = await client.post("/carrier-groups", headers=headers, json={"name": "X"})
    users = await client.get("/users", headers=headers)
    audit = await client.get("/audit", headers=headers)

    assert {settings.status_code, group.status_code, users.status_code} == {
        status(configures)
    }
    assert audit.status_code == status(audits)


@pytest.mark.parametrize(
    ("role", "modules"),
    [
        ("manager", ["audit", "inventory", "operations", "reclassification"]),
        ("controller", ["inventory", "reclassification"]),
        ("operator", ["operations"]),
        ("viewer", []),
    ],
)
async def test_the_ui_gets_the_modules(client, session, role, modules):
    headers = await headers_of(client, session, role)

    me = (await client.get("/auth/me", headers=headers)).json()

    assert me["permissions"] == modules


async def test_the_seed_adds_the_roles_and_updates_descriptions(session):
    session.add(Role(name="operator", description="Wprowadzanie ruchów"))
    await session.flush()

    roles = await seed_roles(session)

    assert list(roles) == [name for name, _ in ROLES]
    assert roles["operator"].description == "Operacje magazynowe"
    assert roles["controller"].description == "Przeksięgowania i inwentaryzacja"
