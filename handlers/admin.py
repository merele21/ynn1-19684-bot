import logging
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from config import ADMIN_IDS, config_manager

router = Router()
logger = logging.getLogger(__name__)


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ═════════════════════════════════════════════════════════════════════════════
# Базовые команды
# ═════════════════════════════════════════════════════════════════════════════

@router.message(Command("start"))
async def cmd_start(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к этому боту.")
        return

    await message.answer(
        "🤖 <b>Telegram Forwarder Bot</b>\n\n"
        "<b>Хештеги:</b>\n"
        "/add_hashtag — Добавить хештег\n"
        "/list_hashtags — Список хештегов\n"
        "/remove_hashtag — Удалить хештег\n\n"
        "<b>Ключевые слова (другие супергруппы):</b>\n"
        "/add_keyword — Добавить правило\n"
        "/list_keywords — Список правил\n"
        "/remove_keyword — Удалить правило\n\n"
        "<b>Утилиты:</b>\n"
        "/get_thread_id — Chat ID + Thread ID\n"
        "/cancel — Отменить текущую операцию\n"
        "/help — Справка",
        parse_mode="HTML"
    )


@router.message(Command("cancel"))
async def cmd_cancel(message: Message):
    """Отмена любого активного FSM-состояния"""
    if not is_admin(message.from_user.id):
        return
    from aiogram.fsm.context import FSMContext
    # cancel обрабатывается через middleware, но добавим ответ
    await message.answer("❌ Операция отменена.")


@router.message(Command("help"))
async def cmd_help(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к этому боту.")
        return

    help_text = """
<b>📖 Справка по командам</b>

━━━━━━━━━━━━━━━━━━━━
<b>ХЕШТЕГИ (SOURCE_CHAT_ID)</b>
━━━━━━━━━━━━━━━━━━━━

<b>/add_hashtag</b> <code>#хештег CHAT_ID THREAD_ID [delay=N]</code>
Добавить хештег. delay — задержка в секундах (0–120).

<b>/list_hashtags</b>
Показать все хештеги.

<b>/remove_hashtag</b> <code>#хештег</code>
Удалить хештег.

━━━━━━━━━━━━━━━━━━━━
<b>КЛЮЧЕВЫЕ СЛОВА (другие группы)</b>
━━━━━━━━━━━━━━━━━━━━

<b>/add_keyword</b>
<code>source=CHAT_ID keyword=слово target=CHAT_ID [thread=ID] [prev=yes/no]</code>

Пример:
<code>/add_keyword source=-1009999999 keyword=итого target=-1008888888 thread=42 prev=yes</code>

• <b>source</b> — ID чата-источника (другая супергруппа)
• <b>keyword</b> — ключевое слово-триггер (без учёта регистра)
• <b>target</b> — куда пересылать
• <b>thread</b> — тред назначения (необязательно)
• <b>prev=yes</b> — пересылать сообщение перед триггером (по умолч. yes)

<b>/list_keywords</b>
Список всех правил.

<b>/remove_keyword</b> <code>source=CHAT_ID keyword=слово</code>
Удалить правило.

━━━━━━━━━━━━━━━━━━━━
<b>УТИЛИТЫ</b>
━━━━━━━━━━━━━━━━━━━━

<b>/get_thread_id</b>
Вызовите в нужном топике — получите Chat ID и Thread ID.

<b>/cancel</b>
Отменить текущую операцию (FSM).
"""
    await message.answer(help_text, parse_mode="HTML")


# ═════════════════════════════════════════════════════════════════════════════
# Управление хештегами
# ═════════════════════════════════════════════════════════════════════════════

@router.message(Command("add_hashtag"))
async def cmd_add_hashtag(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return

    try:
        parts = message.text.split()
        if len(parts) < 4:
            await message.answer(
                "❌ Неверный формат.\n\n"
                "Используйте:\n"
                "<code>/add_hashtag #хештег -100123456789 123 delay=10</code>",
                parse_mode="HTML"
            )
            return

        hashtag = parts[1]
        chat_id = int(parts[2])
        thread_id = int(parts[3])
        delay = 0

        if len(parts) > 4 and parts[4].startswith("delay="):
            raw_delay = int(parts[4].split("=")[1])
            if not (0 <= raw_delay <= 120):
                await message.answer("❌ delay должен быть от 0 до 120 секунд.")
                return
            delay = raw_delay

        if not hashtag.startswith("#"):
            await message.answer("❌ Хештег должен начинаться с символа #")
            return

        await config_manager.add_hashtag(
            hashtag=hashtag,
            chat_id=chat_id,
            thread_id=thread_id,
            delay=delay,
            needs_fsm=False,
            description=f"Добавлено администратором {message.from_user.id}"
        )

        await message.answer(
            f"✅ Хештег <b>{hashtag}</b> добавлен!\n\n"
            f"Чат: <code>{chat_id}</code>\n"
            f"Тред: <code>{thread_id}</code>\n"
            f"Задержка: {delay} сек",
            parse_mode="HTML"
        )

    except (ValueError, IndexError) as e:
        await message.answer(f"❌ Ошибка: {e}")


@router.message(Command("list_hashtags"))
async def cmd_list_hashtags(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return

    hashtags = config_manager.list_hashtags()

    if not hashtags:
        await message.answer("📝 Список хештегов пуст.")
        return

    response = "<b>📋 Хештеги:</b>\n\n"

    for hashtag, cfg in hashtags.items():
        response += f"<b>{hashtag}</b>\n"

        if cfg.get("needs_fsm"):
            response += "├ FSM: ✅\n"
            for opt_type, opt_cfg in cfg.get("options", {}).items():
                response += f"├─ {opt_type}: чат <code>{opt_cfg['chat_id']}</code>, тред <code>{opt_cfg['thread_id']}</code>, delay={opt_cfg.get('delay', 0)}\n"
        else:
            response += (
                f"├ Чат: <code>{cfg.get('chat_id')}</code>\n"
                f"├ Тред: <code>{cfg.get('thread_id')}</code>\n"
                f"└ Delay: {cfg.get('delay', 0)} сек\n"
            )
        response += "\n"

    await message.answer(response, parse_mode="HTML")


@router.message(Command("remove_hashtag"))
async def cmd_remove_hashtag(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return

    parts = message.text.split()
    if len(parts) != 2:
        await message.answer(
            "❌ Используйте: <code>/remove_hashtag #хештег</code>",
            parse_mode="HTML"
        )
        return

    hashtag = parts[1]
    if not hashtag.startswith("#"):
        await message.answer("❌ Хештег должен начинаться с #")
        return

    if await config_manager.remove_hashtag(hashtag):
        await message.answer(f"✅ Хештег <b>{hashtag}</b> удалён.", parse_mode="HTML")
    else:
        await message.answer(f"❌ Хештег <b>{hashtag}</b> не найден.", parse_mode="HTML")


# ═════════════════════════════════════════════════════════════════════════════
# Команда /get_thread_id
# ═════════════════════════════════════════════════════════════════════════════

@router.message(Command("get_thread_id"))
async def cmd_get_thread_id(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return

    chat_id = message.chat.id
    chat_type = message.chat.type
    chat_title = message.chat.title or "Личный чат"
    thread_id = message.message_thread_id if message.is_topic_message else None

    response = (
        f"<b>📊 Информация о текущем чате:</b>\n\n"
        f"<b>Chat ID:</b> <code>{chat_id}</code>\n"
        f"<b>Название:</b> {chat_title}\n"
        f"<b>Тип:</b> {chat_type}\n"
    )

    if thread_id:
        response += (
            f"\n<b>📌 Thread ID:</b> <code>{thread_id}</code>\n"
            f"\n💡 Используйте:\n"
            f"<code>/add_hashtag #хештег {chat_id} {thread_id}</code>"
        )
    elif chat_type in ["group", "supergroup"]:
        response += "\n<i>ℹ️ Это не топик. Вызовите команду внутри нужного топика.</i>"
    else:
        response += "\n<i>ℹ️ Личный чат или канал.</i>"

    await message.reply(response, parse_mode="HTML")


# ═════════════════════════════════════════════════════════════════════════════
# Управление keyword_forwards
# ═════════════════════════════════════════════════════════════════════════════

def _parse_kwargs(text: str) -> dict:
    """
    Парсит строку вида: key1=value1 key2=value2
    Возвращает словарь.
    """
    result = {}
    for part in text.split():
        if "=" in part:
            k, _, v = part.partition("=")
            result[k.strip().lower()] = v.strip()
    return result


@router.message(Command("add_keyword"))
async def cmd_add_keyword(message: Message):
    """
    /add_keyword source=CHAT_ID keyword=слово target=CHAT_ID [thread=ID] [prev=yes/no]
    """
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав.")
        return

    # Убираем саму команду из текста
    raw = message.text.partition(" ")[2].strip()
    if not raw:
        await message.answer(
            "❌ Укажите параметры.\n\n"
            "Пример:\n"
            "<code>/add_keyword source=-1009999999 keyword=итого target=-1008888888 thread=42 prev=yes</code>",
            parse_mode="HTML"
        )
        return

    kw = _parse_kwargs(raw)

    # Обязательные поля
    missing = [f for f in ("source", "keyword", "target") if f not in kw]
    if missing:
        await message.answer(
            f"❌ Не хватает параметров: {', '.join(missing)}\n\n"
            "Обязательные: <b>source</b>, <b>keyword</b>, <b>target</b>",
            parse_mode="HTML"
        )
        return

    try:
        source_chat_id = int(kw["source"])
        target_chat_id = int(kw["target"])
        keyword = kw["keyword"]
        target_thread_id = int(kw["thread"]) if "thread" in kw else None
        forward_previous = kw.get("prev", "yes").lower() not in ("no", "false", "0")
    except ValueError as e:
        await message.answer(f"❌ Ошибка значения: {e}")
        return

    await config_manager.add_keyword_forward(
        source_chat_id=source_chat_id,
        keyword=keyword,
        target_chat_id=target_chat_id,
        target_thread_id=target_thread_id,
        forward_previous=forward_previous,
    )

    await message.answer(
        f"✅ Правило добавлено!\n\n"
        f"Источник: <code>{source_chat_id}</code>\n"
        f"Ключевое слово: <b>{keyword}</b>\n"
        f"Назначение: <code>{target_chat_id}</code>"
        + (f", тред <code>{target_thread_id}</code>" if target_thread_id else "") +
        f"\nПредыдущее сообщение: {'✅' if forward_previous else '❌'}",
        parse_mode="HTML"
    )


@router.message(Command("list_keywords"))
async def cmd_list_keywords(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав.")
        return

    kf_list = config_manager.list_keyword_forwards()

    if not kf_list:
        await message.answer("📝 Нет правил для ключевых слов.")
        return

    response = "<b>📋 Правила ключевых слов:</b>\n\n"
    for i, item in enumerate(kf_list, 1):
        thread = item.get("target_thread_id")
        prev = "✅" if item.get("forward_previous", True) else "❌"
        response += (
            f"<b>{i}.</b> <code>{item.get('source_chat_id')}</code> → "
            f"<b>{item.get('keyword')}</b>\n"
            f"   Назначение: <code>{item.get('target_chat_id')}</code>"
            + (f", тред <code>{thread}</code>" if thread else "") +
            f"\n   Предыдущее: {prev}\n\n"
        )

    await message.answer(response, parse_mode="HTML")


@router.message(Command("remove_keyword"))
async def cmd_remove_keyword(message: Message):
    """
    /remove_keyword source=CHAT_ID keyword=слово
    """
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав.")
        return

    raw = message.text.partition(" ")[2].strip()
    kw = _parse_kwargs(raw)

    if "source" not in kw or "keyword" not in kw:
        await message.answer(
            "❌ Используйте:\n"
            "<code>/remove_keyword source=CHAT_ID keyword=слово</code>",
            parse_mode="HTML"
        )
        return

    try:
        source_chat_id = int(kw["source"])
    except ValueError:
        await message.answer("❌ source должен быть числом.")
        return

    if await config_manager.remove_keyword_forward(source_chat_id, kw["keyword"]):
        await message.answer(f"✅ Правило для <b>{kw['keyword']}</b> удалено.", parse_mode="HTML")
    else:
        await message.answer(f"❌ Правило не найдено.", parse_mode="HTML")