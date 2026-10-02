"""Areas (obszary) the admin assigns to users."""

from uuid import uuid4

from sqlalchemy import func, select

from app.models.user_area import user_areas
from tests.conftest import login, make_user


async def assignment_count(session) -> int:
    """Rows in the link table itself, so an orphaned row cannot hide behind a JOIN."""
    return (
        await session.execute(select(func.count()).select_from(user_areas))
    ).scalar_one()


async def add_area(client, headers, name):
    response = await client.post("/areas", headers=headers, json={"name": name})
    return response.json()["uuid"]


def names(rows):
    return [row["name"] for row in rows]


async def test_admin_creates_a_user_with_areas(client, admin_headers):
    wysylka = await add_area(client, admin_headers, "Wysyłka 445")
    przyjecia = await add_area(client, admin_headers, "Przyjęcia 445")

    response = await client.post(
        "/users",
        headers=admin_headers,
        json={
            "username": "jan",
            "password": "sekret",
            "role": "admin",
            "areas": [wysylka, przyjecia, wysylka],
        },
    )

    assert response.status_code == 200, response.text
    assert names(response.json()["areas"]) == ["Przyjęcia 445", "Wysyłka 445"]

    listed = await client.get("/users", headers=admin_headers)
    jan = next(u for u in listed.json() if u["username"] == "jan")
    assert names(jan["areas"]) == ["Przyjęcia 445", "Wysyłka 445"]


async def test_a_new_user_has_no_areas_by_default(client, admin_headers):
    response = await client.post(
        "/users",
        headers=admin_headers,
        json={"username": "jan", "password": "sekret", "role": "admin"},
    )

    assert response.json()["areas"] == []


async def test_unknown_area_is_rejected(client, admin_headers):
    response = await client.post(
        "/users",
        headers=admin_headers,
        json={
            "username": "jan",
            "password": "sekret",
            "role": "admin",
            "areas": [str(uuid4())],
        },
    )

    assert response.status_code == 400
    assert response.json() == {"message": "Nieznany obszar"}


async def test_update_replaces_keeps_or_clears_areas(client, session, admin_headers):
    a = await add_area(client, admin_headers, "A")
    b = await add_area(client, admin_headers, "B")
    user = await make_user(session, "jan")
    url = f"/users/{user.uuid}"

    replaced = await client.put(url, headers=admin_headers, json={"areas": [a, b]})
    kept = await client.put(url, headers=admin_headers, json={"username": "jan2"})
    cleared = await client.put(url, headers=admin_headers, json={"areas": []})

    assert names(replaced.json()["areas"]) == ["A", "B"]
    assert names(kept.json()["areas"]) == ["A", "B"]
    assert cleared.json()["areas"] == []


async def test_me_lists_only_active_areas(client, session, admin_headers):
    a = await add_area(client, admin_headers, "A")
    b = await add_area(client, admin_headers, "B")
    user = await make_user(session, "jan")
    await client.put(
        f"/users/{user.uuid}", headers=admin_headers, json={"areas": [a, b]}
    )
    await client.put(f"/areas/{b}", headers=admin_headers, json={"is_active": False})

    headers = await login(client, "jan")
    me = await client.get("/auth/me", headers=headers)

    assert names(me.json()["areas"]) == ["A"]


async def test_login_returns_the_areas_too(client, session, admin_headers):
    a = await add_area(client, admin_headers, "A")
    user = await make_user(session, "jan")
    await client.put(f"/users/{user.uuid}", headers=admin_headers, json={"areas": [a]})

    response = await client.post(
        "/auth/login", json={"username": "jan", "password": "Haslo123!"}
    )

    assert names(response.json()["user"]["areas"]) == ["A"]


async def test_deleting_an_area_removes_it_from_users(client, session, admin_headers):
    a = await add_area(client, admin_headers, "A")
    b = await add_area(client, admin_headers, "B")
    user = await make_user(session, "jan")
    await client.put(
        f"/users/{user.uuid}", headers=admin_headers, json={"areas": [a, b]}
    )

    deleted = await client.delete(f"/areas/{a}", headers=admin_headers)
    listed = await client.get("/users", headers=admin_headers)

    assert deleted.status_code == 200
    jan = next(u for u in listed.json() if u["username"] == "jan")
    assert names(jan["areas"]) == ["B"]
    assert await assignment_count(session) == 1


async def test_deleting_a_user_with_areas(client, session, admin_headers):
    a = await add_area(client, admin_headers, "A")
    user = await make_user(session, "jan")
    await client.put(f"/users/{user.uuid}", headers=admin_headers, json={"areas": [a]})

    response = await client.delete(f"/users/{user.uuid}", headers=admin_headers)

    assert response.status_code == 200
    area = await client.get(f"/areas/{a}", headers=admin_headers)
    assert area.status_code == 200
    assert await assignment_count(session) == 0
