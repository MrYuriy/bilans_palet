"""Quality-specific rules; the shared CRUD is covered in test_dictionaries.py."""


async def add(client, headers, name, sort_order):
    return await client.post(
        "/qualities", headers=headers, json={"name": name, "sort_order": sort_order}
    )


async def test_list_is_ordered_by_sort_order_not_name(client, admin_headers):
    await add(client, admin_headers, "Gorsza", 2)
    await add(client, admin_headers, "Lepsza", 1)

    response = await client.get("/qualities", headers=admin_headers)

    assert [(q["name"], q["sort_order"]) for q in response.json()] == [
        ("Lepsza", 1),
        ("Gorsza", 2),
    ]


async def test_sort_order_must_be_unique(client, admin_headers):
    await add(client, admin_headers, "I", 1)

    response = await add(client, admin_headers, "II", 1)

    assert response.status_code == 409
    assert response.json() == {"message": "Jakość o tej kolejności już istnieje"}


async def test_update_to_a_taken_sort_order(client, admin_headers):
    await add(client, admin_headers, "I", 1)
    second = (await add(client, admin_headers, "II", 2)).json()

    response = await client.put(
        f"/qualities/{second['uuid']}", headers=admin_headers, json={"sort_order": 1}
    )

    assert response.status_code == 409
    assert response.json() == {"message": "Jakość o tej kolejności już istnieje"}


async def test_update_keeping_the_same_sort_order(client, admin_headers):
    first = (await add(client, admin_headers, "I", 1)).json()

    response = await client.put(
        f"/qualities/{first['uuid']}",
        headers=admin_headers,
        json={"sort_order": 1, "name": "I gat."},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "I gat."


async def test_sort_order_must_be_positive(client, admin_headers):
    response = await add(client, admin_headers, "Zero", 0)

    assert response.status_code == 422
    assert response.json()["message"] == "Nieprawidłowe dane: sort_order"
