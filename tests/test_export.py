"""XLSX exports: the daily balance (D-1 for LM) and the movement register."""

from datetime import timedelta
from io import BytesIO
from uuid import UUID

import pytest
from openpyxl import load_workbook
from sqlalchemy import insert

from app.models.area import Area
from app.models.pallet_type import PalletType
from app.models.quality import Quality
from app.models.user_area import user_areas
from app.services.day_close_service import DayCloseService
from tests.conftest import login, make_user, warehouse_today

TODAY = warehouse_today()
YESTERDAY = TODAY - timedelta(days=1)
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@pytest.fixture
async def ids(session) -> dict[str, str]:
    rows = {
        "a": Area(name="Przyjęcia 445"),
        "b": Area(name="Wysyłka 445"),
        "eur": PalletType(name="EUR"),
        "I": Quality(name="I", sort_order=1),
    }
    session.add_all(rows.values())
    await session.commit()
    return {key: str(row.uuid) for key, row in rows.items()}


async def move(client, headers, ids, kind, quantity, day, area="a", doc=None):
    response = await client.post(
        "/movements",
        headers=headers,
        json={
            "type": kind,
            "area_uuid": ids[area],
            "operation_date": day.isoformat(),
            "document_number": doc,
            "lines": [
                {
                    "pallet_type_uuid": ids["eur"],
                    "quality_uuid": ids["I"],
                    "quantity": quantity,
                }
            ],
        },
    )
    assert response.status_code == 200, response.text


@pytest.fixture
async def history(client, admin_headers, ids):
    await move(client, admin_headers, ids, "RECEIPT", 100, YESTERDAY, doc="PZ/1")
    await move(client, admin_headers, ids, "SHIPMENT", 30, YESTERDAY, doc="WZ/1")
    await move(client, admin_headers, ids, "RECEIPT", 7, YESTERDAY, area="b")


def sheet_of(response):
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == XLSX
    return load_workbook(BytesIO(response.content)).active


def rows_from(ws, first_row):
    return [
        list(row)
        for row in ws.iter_rows(min_row=first_row, values_only=True)
        if any(v is not None for v in row)
    ]


async def test_daily_balance_file(client, session, admin_headers, history):
    await DayCloseService(session).close_due_days()

    response = await client.get(
        "/balances/daily.xlsx",
        headers=admin_headers,
        params={"day": YESTERDAY.isoformat()},
    )

    assert (
        response.headers["content-disposition"]
        == f'attachment; filename="bilans_{YESTERDAY}.xlsx"'
    )
    ws = sheet_of(response)
    assert ws["A1"].value == "Bilans dzienny palet"
    assert ws["B2"].value.date() == YESTERDAY
    assert ws["B3"].value.startswith("zamknięta")
    assert ws["B4"].value == "wszystkie"
    assert rows_from(ws, 9) == [
        [
            "Obszar",
            "Typ palety",
            "Jakość",
            "Stan otwarcia",
            "Przyjęcia",
            "Wysyłki",
            "Korekty",
            "Przeksięgowania",
            "Stan zamknięcia",
        ],
        ["Przyjęcia 445", "EUR", "I", 0, 100, 30, 0, 0, 70],
        ["Wysyłka 445", "EUR", "I", 0, 7, 0, 0, 0, 7],
        ["RAZEM", "EUR", "I", 0, 107, 30, 0, 0, 77],
    ]


async def test_daily_balance_of_the_open_day_says_preview(
    client, admin_headers, history
):
    response = await client.get(
        "/balances/daily.xlsx", headers=admin_headers, params={"day": TODAY.isoformat()}
    )

    assert sheet_of(response)["B3"].value.startswith("podgląd")


async def test_operator_exports_only_their_area(client, session, ids, history):
    user = await make_user(session, "jan")
    await session.execute(
        insert(user_areas), [{"user_uuid": user.uuid, "area_uuid": UUID(ids["b"])}]
    )
    await session.commit()
    headers = await login(client, "jan")

    balance = sheet_of(
        await client.get(
            "/balances/daily.xlsx",
            headers=headers,
            params={"day": YESTERDAY.isoformat()},
        )
    )
    register = sheet_of(await client.get("/movements/export.xlsx", headers=headers))

    assert balance["B4"].value == "Wysyłka 445"
    assert [r[0] for r in rows_from(balance, 10)] == ["Wysyłka 445", "RAZEM"]
    assert [r[2] for r in rows_from(register, 2)] == ["Wysyłka 445"]


async def test_movement_register_file(client, admin_headers, history):
    response = await client.get("/movements/export.xlsx", headers=admin_headers)

    assert response.headers["content-disposition"].startswith(
        'attachment; filename="rejestr_operacji_'
    )
    ws = sheet_of(response)
    rows = rows_from(ws, 1)
    assert rows[0] == [
        "Data operacji",
        "Operacja",
        "Obszar",
        "Typ palety",
        "Jakość",
        "Zmiana stanu",
        "Nr dokumentu",
        "Komentarz",
        "Użytkownik",
        "Wprowadzono",
    ]
    by_doc = {r[6]: r for r in rows[1:]}
    shipment = by_doc["WZ/1"]
    assert shipment[0].date() == YESTERDAY
    assert shipment[1:6] == ["Wysyłka z magazynu", "Przyjęcia 445", "EUR", "I", -30]
    assert shipment[8] == "admin"
    assert len(rows) == 4


async def test_movement_register_file_follows_the_filters(
    client, admin_headers, history
):
    response = await client.get(
        "/movements/export.xlsx", headers=admin_headers, params={"type": "SHIPMENT"}
    )

    rows = rows_from(sheet_of(response), 2)
    assert [r[1] for r in rows] == ["Wysyłka z magazynu"]


async def test_a_matching_count_is_one_row_with_zero(
    client, admin_headers, ids, history
):
    await client.post(
        "/inventories",
        headers=admin_headers,
        json={
            "area_uuid": ids["b"],
            "lines": [
                {
                    "pallet_type_uuid": ids["eur"],
                    "quality_uuid": ids["I"],
                    "counted_quantity": 7,
                }
            ],
        },
    )

    response = await client.get(
        "/movements/export.xlsx", headers=admin_headers, params={"type": "INVENTORY"}
    )

    rows = rows_from(sheet_of(response), 2)
    assert [r[1:6] for r in rows] == [["Inwentaryzacja", "Wysyłka 445", "—", "—", 0]]


async def test_exports_need_a_login(client):
    for url in ("/balances/daily.xlsx", "/movements/export.xlsx"):
        assert (await client.get(url)).status_code == 401
