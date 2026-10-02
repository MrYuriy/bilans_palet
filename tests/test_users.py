from uuid import uuid4

import pytest

from tests.conftest import login, make_user


async def test_admin_creates_and_lists_users(client, session, admin_headers):
    await make_user(session, "istniejacy", role="operator")

    created = await client.post(
        "/users",
        headers=admin_headers,
        json={
            "username": "jan",
            "password": "sekret",
            "role": "operator",
            "must_change_password": True,
        },
    )

    assert created.status_code == 200, created.text
    body = created.json()
    assert body["username"] == "jan"
    assert body["role"] == "operator"
    assert body["is_active"] is True
    assert body["must_change_password"] is True

    listed = await client.get("/users", headers=admin_headers)
    assert [u["username"] for u in listed.json()] == ["admin", "istniejacy", "jan"]


async def test_created_user_can_log_in(client, admin_headers):
    await client.post(
        "/users",
        headers=admin_headers,
        json={"username": "jan", "password": "sekret", "role": "admin"},
    )

    await login(client, "jan", "sekret")


async def test_create_user_with_unknown_role(client, admin_headers):
    response = await client.post(
        "/users",
        headers=admin_headers,
        json={"username": "jan", "password": "sekret", "role": "duch"},
    )

    assert response.status_code == 400
    assert response.json() == {"message": "Rola 'duch' nie istnieje"}


async def test_create_user_with_a_taken_username(client, admin_headers):
    response = await client.post(
        "/users",
        headers=admin_headers,
        json={"username": "admin", "password": "sekret", "role": "admin"},
    )

    assert response.status_code == 400
    assert response.json() == {"message": "Użytkownik o tym loginie już istnieje"}


async def test_create_user_requires_username_and_password(client, admin_headers):
    response = await client.post(
        "/users",
        headers=admin_headers,
        json={"username": "   ", "password": "sekret", "role": "admin"},
    )

    assert response.status_code == 400
    assert response.json() == {"message": "Login i hasło są wymagane"}


async def test_list_roles(client, session, admin_headers):
    await make_user(session, "jan", role="viewer")

    response = await client.get("/roles", headers=admin_headers)

    assert [r["name"] for r in response.json()] == ["admin", "viewer"]


async def test_admin_updates_a_user(client, session, admin_headers):
    user = await make_user(session, "jan", role="operator")
    await make_user(session, "podglad", role="viewer")

    response = await client.put(
        f"/users/{user.uuid}",
        headers=admin_headers,
        json={
            "username": "jan.kowalski",
            "role": "viewer",
            "must_change_password": True,
            "is_active": False,
        },
    )

    assert response.status_code == 200, response.text
    assert response.json() == {
        "uuid": str(user.uuid),
        "username": "jan.kowalski",
        "role": "viewer",
        "is_active": False,
        "must_change_password": True,
        "areas": [],
    }


async def test_admin_resets_a_password(client, session, admin_headers):
    user = await make_user(session, "jan")

    await client.put(
        f"/users/{user.uuid}", headers=admin_headers, json={"password": "nowe"}
    )

    await login(client, "jan", "nowe")


async def test_update_to_a_taken_username(client, session, admin_headers):
    user = await make_user(session, "jan")

    response = await client.put(
        f"/users/{user.uuid}", headers=admin_headers, json={"username": "admin"}
    )

    assert response.status_code == 400
    assert response.json() == {"message": "Użytkownik o tym loginie już istnieje"}


async def test_update_a_missing_user(client, admin_headers):
    response = await client.put(
        f"/users/{uuid4()}", headers=admin_headers, json={"username": "x"}
    )

    assert response.status_code == 404
    assert response.json() == {"message": "Nie znaleziono użytkownika"}


async def test_admin_cannot_deactivate_themselves(client, session, admin_headers):
    me = await client.get("/auth/me", headers=admin_headers)

    response = await client.put(
        f"/users/{me.json()['uuid']}",
        headers=admin_headers,
        json={"is_active": False},
    )

    assert response.status_code == 403
    assert response.json() == {"message": "Nie możesz dezaktywować własnego konta"}


async def test_admin_deletes_a_user(client, session, admin_headers):
    user = await make_user(session, "jan")

    response = await client.delete(f"/users/{user.uuid}", headers=admin_headers)

    assert response.status_code == 200
    listed = await client.get("/users", headers=admin_headers)
    assert [u["username"] for u in listed.json()] == ["admin"]


async def test_delete_a_missing_user(client, admin_headers):
    response = await client.delete(f"/users/{uuid4()}", headers=admin_headers)

    assert response.status_code == 404


async def test_admin_cannot_delete_themselves(client, admin_headers):
    me = await client.get("/auth/me", headers=admin_headers)

    response = await client.delete(f"/users/{me.json()['uuid']}", headers=admin_headers)

    assert response.status_code == 403
    assert response.json() == {"message": "Nie możesz usunąć własnego konta"}


@pytest.mark.parametrize("role", ["operator", "viewer"])
async def test_only_admin_manages_users(client, session, role):
    target = await make_user(session, "cel")
    await make_user(session, "jan", role=role)
    headers = await login(client, "jan")

    requests = [
        client.get("/users", headers=headers),
        client.get("/roles", headers=headers),
        client.post(
            "/users",
            headers=headers,
            json={"username": "x", "password": "x", "role": role},
        ),
        client.put(f"/users/{target.uuid}", headers=headers, json={"username": "y"}),
        client.delete(f"/users/{target.uuid}", headers=headers),
    ]

    for request in requests:
        response = await request
        assert response.status_code == 403
        assert response.json() == {"message": "Brak uprawnień"}
