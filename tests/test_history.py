"""The stock over time, for the chart."""

from datetime import timedelta

from tests.conftest import line, login, make_user, move, warehouse_today

TODAY = warehouse_today()


async def history(client, headers, days, *types):
    params = [("days", days), *(("type", t) for t in types)]
    response = await client.get("/balances/history", headers=headers, params=params)
    assert response.status_code == 200, response.text
    return [(p["day"], p["quantity"]) for p in response.json()["days"]]


async def test_the_stock_at_the_end_of_each_day(client, admin_headers, carriers):
    ten_days_ago = TODAY - timedelta(days=10)
    two_days_ago = TODAY - timedelta(days=2)
    for kind, ln, day in [
        ("OTHER_RECEIPT", line(carriers.euro, 100), ten_days_ago),
        ("ECOM_TRANSFER", line(carriers.euro, 30), two_days_ago),
        ("OTHER_RECEIPT", line(carriers.single, 5), TODAY),
        ("RECLASSIFICATION", line(carriers.euro, 10, to=carriers.damaged), TODAY),
    ]:
        response = await move(client, admin_headers, kind, ln, day=day)
        assert response.status_code == 200, response.text

    points = await history(client, admin_headers, 4)

    # EURO and Jednorazowe are counted in reports; uszkodzone is not.
    assert points == [
        ((TODAY - timedelta(days=3)).isoformat(), 100),
        (two_days_ago.isoformat(), 70),
        ((TODAY - timedelta(days=1)).isoformat(), 70),
        (TODAY.isoformat(), 65),
    ]


async def test_the_picked_types(client, admin_headers, carriers):
    await move(
        client,
        admin_headers,
        "RECLASSIFICATION",
        line(carriers.euro, 10, to=carriers.damaged),
    )

    damaged = await history(client, admin_headers, 1, carriers.damaged)
    both = await history(client, admin_headers, 1, carriers.euro, carriers.damaged)

    assert damaged == [(TODAY.isoformat(), 10)]
    assert both == [(TODAY.isoformat(), 0)]


async def test_a_period_of_three_months(client, admin_headers, carriers):
    points = await history(client, admin_headers, 90)

    assert len(points) == 90
    assert points[-1][0] == TODAY.isoformat()
    assert {q for _, q in points} == {0}


async def test_the_period_is_limited(client, admin_headers):
    for days in (0, 367):
        response = await client.get(
            "/balances/history", headers=admin_headers, params={"days": days}
        )
        assert response.status_code == 422


async def test_a_viewer_sees_the_history(client, session, carriers):
    await make_user(session, "jan", role="viewer")
    headers = await login(client, "jan")

    assert len(await history(client, headers, 7)) == 7
