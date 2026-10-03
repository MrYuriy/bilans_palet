from datetime import timedelta

from app.core.jwt import create_access_token
from tests.conftest import PASSWORD, login, make_user


async def test_login_returns_token_and_user(client, session):
    await make_user(session, "admin", role="admin")

    response = await client.post(
        "/auth/login", json={"username": "admin", "password": PASSWORD}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["token_type"] == "bearer"
    assert body["user"]["username"] == "admin"
    assert body["user"]["role"] == "admin"
    assert body["user"]["permissions"] == [
        "audit",
        "masterdata",
        "movements",
        "users",
    ]


async def test_login_trims_username(client, session):
    await make_user(session, "jan")

    response = await client.post(
        "/auth/login", json={"username": "  jan ", "password": PASSWORD}
    )

    assert response.status_code == 200


async def test_wrong_password_and_unknown_user_get_the_same_answer(client, session):
    await make_user(session, "jan")

    wrong_password = await client.post(
        "/auth/login", json={"username": "jan", "password": "zle"}
    )
    unknown_user = await client.post(
        "/auth/login", json={"username": "nikt", "password": "zle"}
    )

    for response in (wrong_password, unknown_user):
        assert response.status_code == 401
        assert response.json() == {"message": "Nieprawidłowy login lub hasło"}


async def test_inactive_user_cannot_log_in(client, session):
    await make_user(session, "jan", is_active=False)

    response = await client.post(
        "/auth/login", json={"username": "jan", "password": PASSWORD}
    )

    assert response.status_code == 403
    assert response.json() == {"message": "Konto jest nieaktywne"}


async def test_me_returns_the_current_user(client, session):
    await make_user(session, "jan", role="operator", must_change_password=True)
    headers = await login(client, "jan")

    response = await client.get("/auth/me", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "jan"
    assert body["role"] == "operator"
    assert body["permissions"] == ["movements"]
    assert body["must_change_password"] is True


async def test_me_without_token(client):
    response = await client.get("/auth/me")

    assert response.status_code == 401
    assert response.json() == {"message": "Brak autoryzacji"}


async def test_me_with_a_garbage_token(client):
    response = await client.get(
        "/auth/me", headers={"Authorization": "Bearer nie-token"}
    )

    assert response.status_code == 401
    assert response.json() == {"message": "Sesja wygasła lub token jest nieprawidłowy"}


async def test_me_with_an_expired_token(client, session):
    user = await make_user(session, "jan")
    token = create_access_token(
        {"sub": str(user.uuid)}, expires_delta=timedelta(seconds=-1)
    )

    response = await client.get(
        "/auth/me", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 401


async def test_token_stops_working_once_the_user_is_deactivated(client, session):
    user = await make_user(session, "jan")
    headers = await login(client, "jan")

    user.is_active = False
    await session.commit()

    response = await client.get("/auth/me", headers=headers)

    assert response.status_code == 403
    assert response.json() == {"message": "Konto jest nieaktywne"}


async def test_change_password(client, session):
    await make_user(session, "jan", must_change_password=True)
    headers = await login(client, "jan")

    response = await client.post(
        "/auth/change-password",
        headers=headers,
        json={"old_password": PASSWORD, "new_password": "Nowe456!"},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    new_headers = await login(client, "jan", "Nowe456!")
    me = await client.get("/auth/me", headers=new_headers)
    assert me.json()["must_change_password"] is False

    old = await client.post(
        "/auth/login", json={"username": "jan", "password": PASSWORD}
    )
    assert old.status_code == 401


async def test_change_password_requires_the_current_one(client, session):
    await make_user(session, "jan")
    headers = await login(client, "jan")

    response = await client.post(
        "/auth/change-password",
        headers=headers,
        json={"old_password": "zle", "new_password": "Nowe456!"},
    )

    assert response.status_code == 400
    assert response.json() == {"message": "Nieprawidłowe obecne hasło"}


async def test_change_password_rejects_an_empty_new_one(client, session):
    await make_user(session, "jan")
    headers = await login(client, "jan")

    response = await client.post(
        "/auth/change-password",
        headers=headers,
        json={"old_password": PASSWORD, "new_password": ""},
    )

    assert response.status_code == 400
    assert response.json() == {"message": "Nowe hasło jest wymagane"}
