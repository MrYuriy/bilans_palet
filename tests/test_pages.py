"""The HTML pages and static files are served; the data comes from the API."""

import pytest

from app.routers.pages import templates

PAGES = [
    ("/", "Logowanie"),
    ("/app/haslo", "Zmiana hasła"),
    ("/app/pulpit", "Pulpit"),
    ("/app/bilans", "Bilans dzienny"),
    ("/app/ruchy", "Rejestr operacji"),
    ("/app/nowa-operacja", "Nowa operacja"),
    ("/app/import", "Import z Transplanera"),
    ("/app/inwentaryzacja", "Inwentaryzacja"),
    ("/app/ustawienia", "Ustawienia"),
    ("/app/audyt", "Audyt"),
]


@pytest.mark.parametrize(("url", "title"), PAGES)
async def test_pages_are_served(client, url, title):
    response = await client.get(url)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert f"<title>{title}" in response.text


async def test_assets_carry_a_version(client):
    version = templates.env.globals["asset_version"]

    response = await client.get("/app/pulpit")

    assert f"/static/css/style.css?v={version}" in response.text
    assert f"/static/js/layout.js?v={version}" in response.text


@pytest.mark.parametrize(
    "path", ["/static/css/style.css", "/static/js/api.js", "/static/js/layout.js"]
)
async def test_static_files_are_served(client, path):
    response = await client.get(path)

    assert response.status_code == 200


async def test_an_unknown_page_is_not_found(client):
    response = await client.get("/app/nie-ma")

    assert response.status_code == 404
