import pytest

from bot.db import Database


@pytest.mark.asyncio
async def test_database_flow(tmp_path) -> None:
    db_file = tmp_path / "test.db"
    db = Database(db_file)
    await db.connect()

    user_id = 123456
    p1 = await db.add_pattern(user_id, "Ромб", 0.5)
    p2 = await db.add_pattern(user_id, "Спираль", 1.25)

    calculation_id = await db.create_calculation(
        telegram_id=user_id,
        rack_length=100,
        rattan_width=2,
        basket_diameter=30,
        harness_count=10,
        base_result=471,
        final_result=472.75,
        pattern_ids=[p1, p2],
    )

    history = await db.list_calculations(user_id, page=1, per_page=10)
    assert history.total == 1
    assert history.items[0]["id"] == calculation_id

    card = await db.get_calculation(user_id, calculation_id)
    assert card is not None
    assert len(card["patterns"]) == 2

    updated = await db.update_calculation_notes(user_id, calculation_id, "Тест", "Остаток 0.7")
    assert updated is True

    saved = await db.save_calculation(user_id, calculation_id, "Клумба 30л")
    assert saved is True

    saved_list = await db.list_saved_calculations(user_id, page=1, per_page=10)
    assert saved_list.total == 1
    assert saved_list.items[0]["title"] == "Клумба 30л"

    await db.close()
