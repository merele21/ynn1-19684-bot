"""
keyword_fsm.py
FSM-состояния и вспомогательная клавиатура для настройки keyword-правил.
Не содержит обработчиков сообщений — только StateGroup и фабрику клавиатур.
"""
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


class KeywordForwardMode:
    """Режимы работы keyword-правила"""
    ALL = "all"          # пересылать все сообщения из треда-источника
    KEYWORD = "keyword"  # пересылать только по триггеру + prev media


class KeywordSetupStates(StatesGroup):
    """
    FSM для интерактивной настройки keyword-правила через /add_keyword.
    В текущей реализации /add_keyword принимает всё одной строкой,
    поэтому FSM пока не используется в команде.
    Оставлен как точка расширения для будущего step-by-step wizard.
    """
    choose_mode = State()
    enter_keyword = State()
    confirm = State()


def create_mode_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора режима keyword-правила"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📨 Весь тред (all)",
                    callback_data="kw_mode:all"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔑 По ключевому слову + prev media (keyword)",
                    callback_data="kw_mode:keyword"
                )
            ],
        ]
    )