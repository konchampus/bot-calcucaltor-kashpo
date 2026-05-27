from __future__ import annotations

from math import ceil
from typing import Any

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from .db import Database
from .keyboards import (
    BTN_BACK,
    BTN_CALCULATE,
    BTN_CANCEL,
    BTN_HISTORY,
    BTN_PATTERNS,
    BTN_SAVED,
    calc_step_keyboard,
    calculation_actions_keyboard,
    history_keyboard,
    main_menu_keyboard,
    pattern_delete_keyboard,
    pattern_list_keyboard,
    pattern_menu_keyboard,
    pattern_selector_keyboard,
    review_keyboard,
)
from .services import (
    compute_base_length,
    compute_final_length,
    parse_positive_float,
    parse_positive_int,
)
from .states import BotStates

PER_PAGE = 10


FIELD_TO_STATE = {
    "rack_length": BotStates.calc_rack_length,
    "rattan_width": BotStates.calc_rattan_width,
    "basket_diameter": BotStates.calc_basket_diameter,
    "harness_count": BotStates.calc_harness_count,
}

STATE_ORDER = [
    BotStates.calc_rack_length.state,
    BotStates.calc_rattan_width.state,
    BotStates.calc_basket_diameter.state,
    BotStates.calc_harness_count.state,
]


PROMPTS = {
    BotStates.calc_rack_length.state: "Введите длину стойки:",
    BotStates.calc_rattan_width.state: "Введите ширину ротанга:",
    BotStates.calc_basket_diameter.state: "Введите диаметр корзины:",
    BotStates.calc_harness_count.state: "Введите количество жгутов:",
}


def create_router(db: Database) -> Router:
    router = Router(name="calculator")

    async def ask_field(message: Message, state_name: str, show_back: bool) -> None:
        await message.answer(PROMPTS[state_name], reply_markup=calc_step_keyboard(show_back=show_back))

    async def start_calculation(message: Message, state: FSMContext) -> None:
        await state.clear()
        await state.update_data(selected_pattern_ids=[], editing_state=None)
        await state.set_state(BotStates.calc_rack_length)
        await ask_field(message, BotStates.calc_rack_length.state, show_back=False)

    async def build_review_text(telegram_id: int, state_data: dict[str, Any]) -> str:
        pattern_ids = set(state_data.get("selected_pattern_ids", []))
        patterns = await db.list_patterns(telegram_id)
        selected_patterns = [p for p in patterns if int(p["id"]) in pattern_ids]

        if selected_patterns:
            patterns_text = "\n".join(
                f"- {item['name']}: +{item['value']}" for item in selected_patterns
            )
        else:
            patterns_text = "- без узоров"

        return (
            "Проверка данных:\n"
            f"- Длина стойки: {state_data['rack_length']}\n"
            f"- Ширина ротанга: {state_data['rattan_width']}\n"
            f"- Диаметр корзины: {state_data['basket_diameter']}\n"
            f"- Количество жгутов: {state_data['harness_count']}\n"
            "- Узоры:\n"
            f"{patterns_text}\n\n"
            "Подтвердите расчёт или исправьте поле."
        )

    async def send_pattern_selector(message: Message, telegram_id: int, state: FSMContext, page: int = 1) -> None:
        state_data = await state.get_data()
        selected_ids = set(state_data.get("selected_pattern_ids", []))
        patterns = await db.list_patterns(telegram_id)
        text = (
            "Выберите узоры (можно несколько).\n"
            "После выбора нажмите 'Подтвердить узоры'."
        )
        await message.answer(
            text,
            reply_markup=pattern_selector_keyboard(patterns, selected_ids, page=page, per_page=PER_PAGE),
        )

    async def send_history(message: Message, telegram_id: int, page: int) -> None:
        history = await db.list_calculations(telegram_id, page=page, per_page=PER_PAGE)
        total_pages = max(1, ceil(history.total / PER_PAGE))
        page = min(max(1, page), total_pages)
        text = f"История расчётов (стр. {page}/{total_pages})"
        await message.answer(text, reply_markup=history_keyboard(history.items, page, history.total, prefix="history"))

    async def send_saved(message: Message, telegram_id: int, page: int) -> None:
        saved = await db.list_saved_calculations(telegram_id, page=page, per_page=PER_PAGE)
        total_pages = max(1, ceil(saved.total / PER_PAGE))
        page = min(max(1, page), total_pages)
        text = f"Сохранённые расчёты (стр. {page}/{total_pages})"
        await message.answer(text, reply_markup=history_keyboard(saved.items, page, saved.total, prefix="saved"))

    async def calc_card_text(calc: dict[str, Any], title: str | None = None) -> str:
        patterns = calc.get("patterns", [])
        patterns_text = "\n".join(f"- {item['name']}: +{item['value']}" for item in patterns) if patterns else "- без узоров"
        comment = calc.get("comment") or "-"
        leftovers = calc.get("leftovers_note") or "-"

        parts = []
        if title:
            parts.append(f"Название: {title}")
        parts.append(f"Расчёт #{calc['id']} от {calc['created_at'][:16]}")
        parts.append(f"Длина стойки: {calc['rack_length']}")
        parts.append(f"Ширина ротанга: {calc['rattan_width']}")
        parts.append(f"Диаметр корзины: {calc['basket_diameter']}")
        parts.append(f"Количество жгутов: {calc['harness_count']}")
        parts.append(f"База: {round(calc['base_result'], 3)}")
        parts.append(f"Итог: {round(calc['final_result'], 3)}")
        parts.append("Узоры:\n" + patterns_text)
        parts.append(f"Комментарий: {comment}")
        parts.append(f"Остатки: {leftovers}")
        return "\n".join(parts)

    async def show_calculation_from_callback(
        callback: CallbackQuery,
        telegram_id: int,
        calculation_id: int,
        source: str,
        page: int,
        title: str | None = None,
    ) -> None:
        calc = await db.get_calculation(telegram_id, calculation_id)
        if calc is None:
            await callback.answer("Расчёт не найден", show_alert=True)
            return

        await callback.message.edit_text(
            await calc_card_text(calc, title=title),
            reply_markup=calculation_actions_keyboard(calculation_id, source, page),
        )

    async def safe_edit_reply_markup(callback: CallbackQuery, reply_markup: Any) -> None:
        try:
            await callback.message.edit_reply_markup(reply_markup=reply_markup)
        except TelegramBadRequest as exc:
            if "message is not modified" not in str(exc).lower():
                raise

    async def send_calculation_card(
        message: Message,
        telegram_id: int,
        calculation_id: int,
        source: str,
        page: int,
    ) -> None:
        calc = await db.get_calculation(telegram_id, calculation_id)
        if calc is None:
            await message.answer("Расчёт не найден.", reply_markup=main_menu_keyboard())
            return
        await message.answer(
            await calc_card_text(calc),
            reply_markup=calculation_actions_keyboard(calculation_id, source, page),
        )

    @router.message(CommandStart())
    async def on_start(message: Message, state: FSMContext) -> None:
        await state.clear()
        await db._ensure_user(message.from_user.id)
        await message.answer(
            "Бот для расчёта длины жгута готов к работе.",
            reply_markup=main_menu_keyboard(),
        )

    @router.message(Command("help"))
    async def on_help(message: Message) -> None:
        await message.answer(
            "Используйте кнопки меню: Рассчитать, История, Сохранённые, Узоры."
        )

    @router.message(Command("cancel"))
    async def command_cancel(message: Message, state: FSMContext) -> None:
        await state.clear()
        await message.answer("Действие отменено.", reply_markup=main_menu_keyboard())

    @router.message(StateFilter("*"), F.text == BTN_CANCEL)
    async def text_cancel(message: Message, state: FSMContext) -> None:
        await state.clear()
        await message.answer("Действие отменено.", reply_markup=main_menu_keyboard())

    @router.message(F.text == BTN_CALCULATE)
    async def menu_calculate(message: Message, state: FSMContext) -> None:
        await start_calculation(message, state)

    @router.message(F.text == BTN_HISTORY)
    async def menu_history(message: Message) -> None:
        await send_history(message, message.from_user.id, page=1)

    @router.message(F.text == BTN_SAVED)
    async def menu_saved(message: Message) -> None:
        await send_saved(message, message.from_user.id, page=1)

    @router.message(F.text == BTN_PATTERNS)
    async def menu_patterns(message: Message) -> None:
        await message.answer("Раздел узоров:", reply_markup=pattern_menu_keyboard())

    @router.callback_query(F.data == "noop")
    async def noop_handler(callback: CallbackQuery) -> None:
        await callback.answer()

    @router.message(
        StateFilter(
            BotStates.calc_rattan_width,
            BotStates.calc_basket_diameter,
            BotStates.calc_harness_count,
            BotStates.calc_select_patterns,
            BotStates.calc_review,
            BotStates.calc_rack_length,
        ),
        F.text == BTN_BACK,
    )
    async def back_in_calculation(message: Message, state: FSMContext) -> None:
        current_state = await state.get_state()
        data = await state.get_data()
        editing_state = data.get("editing_state")

        if editing_state and current_state == editing_state:
            await state.update_data(editing_state=None)
            await state.set_state(BotStates.calc_review)
            review_text = await build_review_text(message.from_user.id, await state.get_data())
            await message.answer(review_text, reply_markup=review_keyboard())
            return

        if current_state == BotStates.calc_rack_length.state:
            await message.answer("Это первый шаг.", reply_markup=calc_step_keyboard(show_back=False))
            return

        previous = {
            BotStates.calc_rattan_width.state: BotStates.calc_rack_length.state,
            BotStates.calc_basket_diameter.state: BotStates.calc_rattan_width.state,
            BotStates.calc_harness_count.state: BotStates.calc_basket_diameter.state,
            BotStates.calc_select_patterns.state: BotStates.calc_harness_count.state,
            BotStates.calc_review.state: BotStates.calc_select_patterns.state,
        }.get(current_state)

        if previous is None:
            return

        await state.set_state(previous)
        await ask_field(message, previous, show_back=(previous != BotStates.calc_rack_length.state))

    @router.message(BotStates.calc_rack_length)
    async def set_rack_length(message: Message, state: FSMContext) -> None:
        try:
            value = parse_positive_float(message.text)
        except Exception:
            await message.answer("Нужно число > 0. Попробуйте снова.")
            return

        await state.update_data(rack_length=value)
        data = await state.get_data()
        if data.get("editing_state") == BotStates.calc_rack_length.state:
            await state.update_data(editing_state=None)
            await state.set_state(BotStates.calc_review)
            await message.answer(
                await build_review_text(message.from_user.id, await state.get_data()),
                reply_markup=review_keyboard(),
            )
            return

        await state.set_state(BotStates.calc_rattan_width)
        await ask_field(message, BotStates.calc_rattan_width.state, show_back=True)

    @router.message(BotStates.calc_rattan_width)
    async def set_rattan_width(message: Message, state: FSMContext) -> None:
        try:
            value = parse_positive_float(message.text)
        except Exception:
            await message.answer("Нужно число > 0. Попробуйте снова.")
            return

        await state.update_data(rattan_width=value)
        data = await state.get_data()
        if data.get("editing_state") == BotStates.calc_rattan_width.state:
            await state.update_data(editing_state=None)
            await state.set_state(BotStates.calc_review)
            await message.answer(
                await build_review_text(message.from_user.id, await state.get_data()),
                reply_markup=review_keyboard(),
            )
            return

        await state.set_state(BotStates.calc_basket_diameter)
        await ask_field(message, BotStates.calc_basket_diameter.state, show_back=True)

    @router.message(BotStates.calc_basket_diameter)
    async def set_basket_diameter(message: Message, state: FSMContext) -> None:
        try:
            value = parse_positive_float(message.text)
        except Exception:
            await message.answer("Нужно число > 0. Попробуйте снова.")
            return

        await state.update_data(basket_diameter=value)
        data = await state.get_data()
        if data.get("editing_state") == BotStates.calc_basket_diameter.state:
            await state.update_data(editing_state=None)
            await state.set_state(BotStates.calc_review)
            await message.answer(
                await build_review_text(message.from_user.id, await state.get_data()),
                reply_markup=review_keyboard(),
            )
            return

        await state.set_state(BotStates.calc_harness_count)
        await ask_field(message, BotStates.calc_harness_count.state, show_back=True)

    @router.message(BotStates.calc_harness_count)
    async def set_harness_count(message: Message, state: FSMContext) -> None:
        try:
            value = parse_positive_int(message.text)
        except Exception:
            await message.answer("Нужно целое число > 0. Попробуйте снова.")
            return

        await state.update_data(harness_count=value)
        data = await state.get_data()
        if data.get("editing_state") == BotStates.calc_harness_count.state:
            await state.update_data(editing_state=None)
            await state.set_state(BotStates.calc_review)
            await message.answer(
                await build_review_text(message.from_user.id, await state.get_data()),
                reply_markup=review_keyboard(),
            )
            return

        await state.set_state(BotStates.calc_select_patterns)
        await send_pattern_selector(message, message.from_user.id, state, page=1)

    @router.callback_query(BotStates.calc_select_patterns, F.data.startswith("calc_patterns:"))
    async def handle_calc_patterns(callback: CallbackQuery, state: FSMContext) -> None:
        parts = callback.data.split(":")
        action = parts[1]
        data = await state.get_data()
        selected_ids = set(data.get("selected_pattern_ids", []))
        patterns = await db.list_patterns(callback.from_user.id)

        if action == "toggle":
            pattern_id = int(parts[2])
            page = int(parts[3])
            if pattern_id in selected_ids:
                selected_ids.remove(pattern_id)
            else:
                selected_ids.add(pattern_id)
            await state.update_data(selected_pattern_ids=list(selected_ids))
            await safe_edit_reply_markup(
                callback,
                pattern_selector_keyboard(patterns, selected_ids, page=page, per_page=PER_PAGE),
            )

        elif action == "page":
            page = int(parts[2])
            await safe_edit_reply_markup(
                callback,
                pattern_selector_keyboard(patterns, selected_ids, page=page, per_page=PER_PAGE),
            )

        elif action == "clear":
            if not selected_ids:
                await callback.answer("Узоры уже очищены")
                return
            await state.update_data(selected_pattern_ids=[])
            await safe_edit_reply_markup(
                callback,
                pattern_selector_keyboard(patterns, set(), page=1, per_page=PER_PAGE),
            )
            await callback.answer("Выбор узоров очищен")
            return

        elif action == "back":
            await state.set_state(BotStates.calc_harness_count)
            await callback.message.answer(
                PROMPTS[BotStates.calc_harness_count.state],
                reply_markup=calc_step_keyboard(show_back=True),
            )

        elif action == "confirm":
            await state.set_state(BotStates.calc_review)
            await callback.message.answer(
                await build_review_text(callback.from_user.id, await state.get_data()),
                reply_markup=review_keyboard(),
            )

        await callback.answer()

    @router.callback_query(BotStates.calc_review, F.data.startswith("review:"))
    async def handle_review(callback: CallbackQuery, state: FSMContext) -> None:
        parts = callback.data.split(":")
        action = parts[1]

        if action == "cancel":
            await state.clear()
            await callback.message.answer("Расчёт отменён.", reply_markup=main_menu_keyboard())
            await callback.answer()
            return

        if action == "edit":
            field = parts[2]
            target_state = FIELD_TO_STATE[field]
            await state.update_data(editing_state=target_state.state)
            await state.set_state(target_state)
            await callback.message.answer(PROMPTS[target_state.state], reply_markup=calc_step_keyboard(show_back=True))
            await callback.answer()
            return

        data = await state.get_data()
        pattern_ids = [int(item) for item in data.get("selected_pattern_ids", [])]
        all_patterns = await db.list_patterns(callback.from_user.id)
        selected_patterns = [item for item in all_patterns if int(item["id"]) in pattern_ids]
        pattern_values = [float(item["value"]) for item in selected_patterns]

        base = compute_base_length(
            float(data["rack_length"]),
            float(data["rattan_width"]),
            float(data["basket_diameter"]),
            int(data["harness_count"]),
        )
        final = compute_final_length(base, pattern_values)

        calculation_id = await db.create_calculation(
            telegram_id=callback.from_user.id,
            rack_length=float(data["rack_length"]),
            rattan_width=float(data["rattan_width"]),
            basket_diameter=float(data["basket_diameter"]),
            harness_count=int(data["harness_count"]),
            base_result=base,
            final_result=final,
            pattern_ids=pattern_ids,
        )

        await state.clear()
        await callback.message.answer("Расчёт выполнен.", reply_markup=main_menu_keyboard())
        await callback.message.answer(
            f"Итоговая длина одного жгута: {final}",
            reply_markup=calculation_actions_keyboard(calculation_id, source="recent", page=1),
        )
        await callback.answer()

    @router.callback_query(F.data.startswith("calc_action:"))
    async def calc_action(callback: CallbackQuery, state: FSMContext) -> None:
        _, action, calc_id_raw, source, page_raw = callback.data.split(":")
        calculation_id = int(calc_id_raw)
        page = int(page_raw)

        if action == "done":
            if source == "history":
                history = await db.list_calculations(callback.from_user.id, page=page, per_page=PER_PAGE)
                await callback.message.edit_text(
                    f"История расчётов (стр. {page})",
                    reply_markup=history_keyboard(history.items, page, history.total, prefix="history"),
                )
            elif source == "saved":
                saved = await db.list_saved_calculations(callback.from_user.id, page=page, per_page=PER_PAGE)
                await callback.message.edit_text(
                    f"Сохранённые расчёты (стр. {page})",
                    reply_markup=history_keyboard(saved.items, page, saved.total, prefix="saved"),
                )
            else:
                await callback.message.edit_reply_markup(reply_markup=None)
            await callback.answer()
            return

        await state.set_state(BotStates.comment_text if action == "comment" else BotStates.save_title)
        await state.update_data(action=action, target_calc_id=calculation_id, return_source=source, return_page=page)

        if action == "comment":
            await callback.message.answer("Введите комментарий к расчёту:", reply_markup=calc_step_keyboard(show_back=True))
        else:
            await callback.message.answer("Введите название для сохранения:", reply_markup=calc_step_keyboard(show_back=True))
        await callback.answer()

    @router.message(BotStates.comment_text, F.text == BTN_BACK)
    @router.message(BotStates.save_title, F.text == BTN_BACK)
    async def back_from_calc_actions(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        calc_id = int(data.get("target_calc_id", 0))
        source = data.get("return_source", "recent")
        page = int(data.get("return_page", 1))
        await state.clear()
        if calc_id == 0:
            await message.answer("Не удалось вернуться к расчёту.", reply_markup=main_menu_keyboard())
            return
        await message.answer("Возврат к карточке расчёта.", reply_markup=main_menu_keyboard())
        await send_calculation_card(message, message.from_user.id, calc_id, source, page)

    @router.message(BotStates.comment_text)
    async def set_comment(message: Message, state: FSMContext) -> None:
        await state.update_data(comment_text=message.text.strip())
        await state.set_state(BotStates.leftovers_text)
        await message.answer(
            "Введите заметку по остаткам (или '-' чтобы пропустить):",
            reply_markup=calc_step_keyboard(show_back=True),
        )

    @router.message(BotStates.leftovers_text, F.text == BTN_BACK)
    async def back_to_comment(message: Message, state: FSMContext) -> None:
        await state.set_state(BotStates.comment_text)
        await message.answer("Введите комментарий к расчёту:", reply_markup=calc_step_keyboard(show_back=True))

    @router.message(BotStates.leftovers_text)
    async def set_leftovers(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        leftovers = message.text.strip()
        leftovers_value = None if leftovers == "-" else leftovers

        ok = await db.update_calculation_notes(
            telegram_id=message.from_user.id,
            calculation_id=int(data["target_calc_id"]),
            comment=data.get("comment_text", ""),
            leftovers_note=leftovers_value,
        )
        if not ok:
            await state.clear()
            await message.answer("Не удалось обновить комментарий.", reply_markup=main_menu_keyboard())
            return

        calc = await db.get_calculation(message.from_user.id, int(data["target_calc_id"]))
        source = data.get("return_source", "recent")
        page = int(data.get("return_page", 1))

        await state.clear()
        await message.answer("Комментарий сохранён.", reply_markup=main_menu_keyboard())
        if calc is not None:
            await message.answer(
                await calc_card_text(calc),
                reply_markup=calculation_actions_keyboard(calc["id"], source=source, page=page),
            )

    @router.message(BotStates.save_title)
    async def set_save_title(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        title = message.text.strip()
        if not title:
            await message.answer("Название не может быть пустым.")
            return

        ok = await db.save_calculation(
            telegram_id=message.from_user.id,
            calculation_id=int(data["target_calc_id"]),
            title=title,
        )
        await state.clear()

        if not ok:
            await message.answer("Не удалось сохранить расчёт.", reply_markup=main_menu_keyboard())
            return

        await message.answer("Расчёт сохранён с названием.", reply_markup=main_menu_keyboard())

    @router.callback_query(F.data.startswith("history:page:"))
    async def history_page(callback: CallbackQuery) -> None:
        page = int(callback.data.split(":")[2])
        history = await db.list_calculations(callback.from_user.id, page=page, per_page=PER_PAGE)
        await callback.message.edit_text(
            f"История расчётов (стр. {page})",
            reply_markup=history_keyboard(history.items, page, history.total, prefix="history"),
        )
        await callback.answer()

    @router.callback_query(F.data.startswith("history:open:"))
    async def history_open(callback: CallbackQuery) -> None:
        _, _, calc_id_raw, page_raw = callback.data.split(":")
        await show_calculation_from_callback(
            callback,
            telegram_id=callback.from_user.id,
            calculation_id=int(calc_id_raw),
            source="history",
            page=int(page_raw),
        )
        await callback.answer()

    @router.callback_query(F.data.startswith("saved:page:"))
    async def saved_page(callback: CallbackQuery) -> None:
        page = int(callback.data.split(":")[2])
        saved = await db.list_saved_calculations(callback.from_user.id, page=page, per_page=PER_PAGE)
        await callback.message.edit_text(
            f"Сохранённые расчёты (стр. {page})",
            reply_markup=history_keyboard(saved.items, page, saved.total, prefix="saved"),
        )
        await callback.answer()

    @router.callback_query(F.data.startswith("saved:open:"))
    async def saved_open(callback: CallbackQuery) -> None:
        _, _, calc_id_raw, page_raw = callback.data.split(":")
        await show_calculation_from_callback(
            callback,
            telegram_id=callback.from_user.id,
            calculation_id=int(calc_id_raw),
            source="saved",
            page=int(page_raw),
        )
        await callback.answer()

    @router.callback_query(F.data.startswith("pattern_menu:"))
    async def pattern_menu(callback: CallbackQuery, state: FSMContext) -> None:
        parts = callback.data.split(":")
        action = parts[1]

        if action == "home":
            await callback.message.edit_text("Раздел узоров:", reply_markup=pattern_menu_keyboard())
            await callback.answer()
            return

        if action == "add":
            await state.set_state(BotStates.pattern_name)
            await callback.message.answer("Введите название узора:", reply_markup=calc_step_keyboard(show_back=False))
            await callback.answer()
            return

        page = int(parts[2])
        patterns = await db.list_patterns(callback.from_user.id)

        if action == "list":
            if not patterns:
                await callback.message.edit_text("Узоров пока нет.", reply_markup=pattern_menu_keyboard())
                await callback.answer()
                return
            lines = [f"- {item['name']}: +{item['value']}" for item in patterns[(page - 1) * PER_PAGE : page * PER_PAGE]]
            total_pages = max(1, ceil(len(patterns) / PER_PAGE))
            text = "Список узоров:\n" + "\n".join(lines) + f"\n\nСтраница {page}/{total_pages}"
            keyboard = pattern_list_keyboard(page=page, total_pages=total_pages)
            await callback.message.edit_text(text, reply_markup=keyboard)

        if action == "delete":
            await callback.message.edit_text(
                "Выберите узор для удаления:",
                reply_markup=pattern_delete_keyboard(patterns, page=page),
            )

        await callback.answer()

    @router.callback_query(F.data.startswith("pattern_delete:item:"))
    async def pattern_delete(callback: CallbackQuery) -> None:
        _, _, _, pattern_id_raw, page_raw = callback.data.split(":")
        pattern_id = int(pattern_id_raw)
        page = int(page_raw)
        await db.delete_pattern(callback.from_user.id, pattern_id)

        patterns = await db.list_patterns(callback.from_user.id)
        await callback.message.edit_text(
            "Выберите узор для удаления:",
            reply_markup=pattern_delete_keyboard(patterns, page=page),
        )
        await callback.answer("Узор удалён")

    @router.message(BotStates.pattern_name)
    async def pattern_name(message: Message, state: FSMContext) -> None:
        name = message.text.strip()
        if not name:
            await message.answer("Название не должно быть пустым.")
            return
        await state.update_data(pattern_name=name)
        await state.set_state(BotStates.pattern_value)
        await message.answer("Введите добавку узора (число > 0):")

    @router.message(BotStates.pattern_value)
    async def pattern_value(message: Message, state: FSMContext) -> None:
        try:
            value = parse_positive_float(message.text)
        except Exception:
            await message.answer("Нужно число > 0.")
            return

        data = await state.get_data()
        await db.add_pattern(message.from_user.id, data["pattern_name"], value)
        await state.clear()
        await message.answer("Узор добавлен.", reply_markup=main_menu_keyboard())
        await message.answer("Раздел узоров:", reply_markup=pattern_menu_keyboard())

    @router.message()
    async def fallback(message: Message) -> None:
        await message.answer("Используйте кнопки меню ниже.", reply_markup=main_menu_keyboard())

    return router
