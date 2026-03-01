"""
bot_commands.py
Список команд для регистрации в интерфейсе Telegram (кнопка "/").
Редактируйте только этот файл, чтобы изменить меню бота.
"""
from aiogram.types import BotCommand

BOT_COMMANDS: list[BotCommand] = [
    # ── Основные ────────────────────────────────────────────────────────────
    BotCommand(command="start",          description="Запустить бота / список команд"),
    BotCommand(command="help",           description="Подробная справка"),
    BotCommand(command="cancel",         description="Отменить текущую операцию"),

    # ── Хештеги (SOURCE_CHAT_ID) ────────────────────────────────────────────
    BotCommand(command="add_hashtag",    description="Добавить хештег для пересылки"),
    BotCommand(command="list_hashtags",  description="Список всех хештегов"),
    BotCommand(command="remove_hashtag", description="Удалить хештег"),

    # ── Keyword-правила (другие супергруппы) ────────────────────────────────
    BotCommand(command="add_keyword",    description="Добавить правило по ключевому слову"),
    BotCommand(command="list_keywords",  description="Список правил ключевых слов"),
    BotCommand(command="remove_keyword", description="Удалить правило ключевого слова"),

    # ── Утилиты ─────────────────────────────────────────────────────────────
    BotCommand(command="get_thread_id",  description="Получить Chat ID и Thread ID"),
]