from aiogram.fsm.state import State, StatesGroup


class BotStates(StatesGroup):
    calc_rack_length = State()
    calc_rattan_width = State()
    calc_basket_diameter = State()
    calc_harness_count = State()
    calc_select_patterns = State()
    calc_review = State()

    pattern_name = State()
    pattern_value = State()

    comment_text = State()
    leftovers_text = State()
    save_title = State()
