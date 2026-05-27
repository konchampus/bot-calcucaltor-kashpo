from __future__ import annotations

from math import ceil

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

BTN_CALCULATE = "Рассчитать"
BTN_HISTORY = "История"
BTN_SAVED = "Сохранённые"
BTN_PATTERNS = "Узоры"
BTN_BACK = "Назад"
BTN_CANCEL = "Отмена"


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_CALCULATE)],
            [KeyboardButton(text=BTN_HISTORY), KeyboardButton(text=BTN_SAVED)],
            [KeyboardButton(text=BTN_PATTERNS)],
        ],
        resize_keyboard=True,
    )


def calc_step_keyboard(show_back: bool = True) -> ReplyKeyboardMarkup:
    rows: list[list[KeyboardButton]] = []
    if show_back:
        rows.append([KeyboardButton(text=BTN_BACK)])
    rows.append([KeyboardButton(text=BTN_CANCEL)])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def review_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🟢 Подтвердить", callback_data="review:confirm")],
            [InlineKeyboardButton(text="🟡 Длина стойки", callback_data="review:edit:rack_length")],
            [InlineKeyboardButton(text="🟡 Ширина ротанга", callback_data="review:edit:rattan_width")],
            [InlineKeyboardButton(text="🟡 Диаметр корзины", callback_data="review:edit:basket_diameter")],
            [InlineKeyboardButton(text="🟡 Кол-во жгутов", callback_data="review:edit:harness_count")],
            [InlineKeyboardButton(text="🔴 Отмена", callback_data="review:cancel")],
        ]
    )


def pattern_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Добавить узор", callback_data="pattern_menu:add")],
            [InlineKeyboardButton(text="Список узоров", callback_data="pattern_menu:list:1")],
            [InlineKeyboardButton(text="Удалить узор", callback_data="pattern_menu:delete:1")],
        ]
    )


def pattern_selector_keyboard(
    patterns: list[dict],
    selected_ids: set[int],
    page: int,
    per_page: int = 10,
) -> InlineKeyboardMarkup:
    total_pages = max(1, ceil(len(patterns) / per_page))
    page = min(max(1, page), total_pages)
    start = (page - 1) * per_page
    end = start + per_page

    buttons: list[list[InlineKeyboardButton]] = []
    for pattern in patterns[start:end]:
        marker = "[x]" if int(pattern["id"]) in selected_ids else "[ ]"
        label = f"{marker} {pattern['name']} (+{pattern['value']})"
        callback = f"calc_patterns:toggle:{pattern['id']}:{page}"
        buttons.append([InlineKeyboardButton(text=label, callback_data=callback)])

    nav_row: list[InlineKeyboardButton] = []
    if page > 1:
        nav_row.append(InlineKeyboardButton(text="<", callback_data=f"calc_patterns:page:{page - 1}"))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton(text=">", callback_data=f"calc_patterns:page:{page + 1}"))
    if nav_row:
        buttons.append(nav_row)

    buttons.append([InlineKeyboardButton(text="Подтвердить узоры", callback_data="calc_patterns:confirm")])
    buttons.append([InlineKeyboardButton(text="Без узоров", callback_data="calc_patterns:clear")])
    buttons.append([InlineKeyboardButton(text="Назад к шагу", callback_data="calc_patterns:back")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def history_keyboard(items: list[dict], page: int, total: int, prefix: str) -> InlineKeyboardMarkup:
    per_page = 10
    total_pages = max(1, ceil(total / per_page))
    buttons: list[list[InlineKeyboardButton]] = []

    if prefix == "history":
        for item in items:
            text = f"#{item['id']} | {item['final_result']} | {item['created_at'][:16]}"
            callback_data = f"history:open:{item['id']}:{page}"
            buttons.append([InlineKeyboardButton(text=text, callback_data=callback_data)])
    else:
        for item in items:
            text = f"{item['title']} | {item['final_result']}"
            callback_data = f"saved:open:{item['calculation_id']}:{page}"
            buttons.append([InlineKeyboardButton(text=text, callback_data=callback_data)])

    nav_row: list[InlineKeyboardButton] = []
    if page > 1:
        nav_row.append(
            InlineKeyboardButton(
                text="<",
                callback_data=("history" if prefix == "history" else "saved") + f":page:{page - 1}",
            )
        )
    if page < total_pages:
        nav_row.append(
            InlineKeyboardButton(
                text=">",
                callback_data=("history" if prefix == "history" else "saved") + f":page:{page + 1}",
            )
        )
    if nav_row:
        buttons.append(nav_row)

    return InlineKeyboardMarkup(inline_keyboard=buttons or [[InlineKeyboardButton(text="Пусто", callback_data="noop")]])


def calculation_actions_keyboard(calc_id: int, source: str, page: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🟡 Добавить комментарий", callback_data=f"calc_action:comment:{calc_id}:{source}:{page}")],
            [InlineKeyboardButton(text="🟢 Сохранить с названием", callback_data=f"calc_action:save:{calc_id}:{source}:{page}")],
            [InlineKeyboardButton(text="✅ Готово", callback_data=f"calc_action:done:{calc_id}:{source}:{page}")],
        ]
    )


def pattern_delete_keyboard(patterns: list[dict], page: int, per_page: int = 10) -> InlineKeyboardMarkup:
    total_pages = max(1, ceil(len(patterns) / per_page))
    page = min(max(1, page), total_pages)
    start = (page - 1) * per_page
    end = start + per_page

    buttons: list[list[InlineKeyboardButton]] = []
    for pattern in patterns[start:end]:
        callback = f"pattern_delete:item:{pattern['id']}:{page}"
        buttons.append([InlineKeyboardButton(text=f"Удалить: {pattern['name']}", callback_data=callback)])

    nav_row: list[InlineKeyboardButton] = []
    if page > 1:
        nav_row.append(InlineKeyboardButton(text="<", callback_data=f"pattern_menu:delete:{page - 1}"))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton(text=">", callback_data=f"pattern_menu:delete:{page + 1}"))
    if nav_row:
        buttons.append(nav_row)

    buttons.append([InlineKeyboardButton(text="К меню узоров", callback_data="pattern_menu:home")])
    return InlineKeyboardMarkup(inline_keyboard=buttons or [[InlineKeyboardButton(text="Пусто", callback_data="noop")]])


def pattern_list_keyboard(page: int, total_pages: int) -> InlineKeyboardMarkup:
    buttons: list[list[InlineKeyboardButton]] = []
    nav_row: list[InlineKeyboardButton] = []

    if page > 1:
        nav_row.append(InlineKeyboardButton(text="<", callback_data=f"pattern_menu:list:{page - 1}"))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton(text=">", callback_data=f"pattern_menu:list:{page + 1}"))
    if nav_row:
        buttons.append(nav_row)

    buttons.append([InlineKeyboardButton(text="К меню узоров", callback_data="pattern_menu:home")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
