import logging
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from config import ADMIN_IDS, config_manager
from commands.commands_config import (
    START_TEXT, HELP_TEXT,
    CMD_ADD_HASHTAG_USAGE, CMD_REMOVE_HASHTAG_USAGE,
    CMD_ADD_KEYWORD_USAGE, CMD_REMOVE_KEYWORD_USAGE,
)

router = Router()
logger = logging.getLogger(__name__)


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def _parse_kwargs(text: str) -> dict:
    """
    Парсит строку вида:
        key1=value1 key2="составное значение" key3=value3

    Значения в кавычках (одинарных или двойных) воспринимаются как единое целое.
    Кавычки из значения отбрасываются.

    Примеры:
        'source=-100123 keyword="товар дня" target=-100456'
        → {'source': '-100123', 'keyword': 'товар дня', 'target': '-100456'}

        "keyword='закрыт* смен*' mode=keyword"
        → {'keyword': 'закрыт* смен*', 'mode': 'keyword'}
    """
    import re
    result = {}
    pattern = re.compile(
        r'(\w+)'          # ключ
        r'='               # разделитель
        r'(?:'
        r'"([^"]*)"' # значение в двойных кавычках
        r"|"
        r"'([^']*)'"  # значение в одинарных кавычках
        r'|'
        r'(\S+)'          # значение без кавычек (до следующего пробела)
        r')'
    )
    for m in pattern.finditer(text):
        key = m.group(1).lower()
        value = (m.group(2) if m.group(2) is not None else
                 m.group(3) if m.group(3) is not None else
                 m.group(4) or "")
        result[key] = value
    return result


# ═════════════════════════════════════════════════════════════════════════════
# Базовые команды
# ═════════════════════════════════════════════════════════════════════════════

@router.message(Command("start"))
async def cmd_start(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к этому боту.")
        return
    await message.answer(START_TEXT, parse_mode="HTML")


@router.message(Command("help"))
async def cmd_help(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к этому боту.")
        return
    await message.answer(HELP_TEXT, parse_mode="HTML")


# ═════════════════════════════════════════════════════════════════════════════
# Управление хештегами
# ═════════════════════════════════════════════════════════════════════════════

@router.message(Command("add_hashtag"))
async def cmd_add_hashtag(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Нет прав.")
        return
    try:
        parts = message.text.split()
        if len(parts) < 4:
            await message.answer(CMD_ADD_HASHTAG_USAGE, parse_mode="HTML")
            return

        hashtag = parts[1]
        if not hashtag.startswith("#"):
            await message.answer("❌ Хештег должен начинаться с #")
            return

        chat_id = int(parts[2])
        thread_id = int(parts[3])
        delay = 0

        if len(parts) > 4 and parts[4].startswith("delay="):
            raw = int(parts[4].split("=")[1])
            if not (0 <= raw <= 120):
                await message.answer("❌ delay должен быть от 0 до 120 секунд.")
                return
            delay = raw

        await config_manager.add_hashtag(
            hashtag=hashtag,
            chat_id=chat_id,
            thread_id=thread_id,
            delay=delay,
            needs_fsm=False,
            description=f"Добавлено администратором {message.from_user.id}",
        )
        await message.answer(
            f"✅ Хештег <b>{hashtag}</b> добавлен!\n\n"
            f"Чат: <code>{chat_id}</code>\n"
            f"Тред: <code>{thread_id}</code>\n"
            f"Задержка: {delay} сек",
            parse_mode="HTML",
        )
    except (ValueError, IndexError) as e:
        await message.answer(f"❌ Ошибка: {e}")


@router.message(Command("list_hashtags"))
async def cmd_list_hashtags(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Нет прав.")
        return

    hashtags = config_manager.list_hashtags()
    if not hashtags:
        await message.answer("📝 Список хештегов пуст.")
        return

    lines = ["<b>📋 Хештеги:</b>\n"]
    for tag, cfg in hashtags.items():
        lines.append(f"<b>{tag}</b>")
        if cfg.get("needs_fsm"):
            lines.append("├ FSM: ✅")
            for opt, ocfg in cfg.get("options", {}).items():
                lines.append(
                    f"├─ {opt}: чат <code>{ocfg['chat_id']}</code>, "
                    f"тред <code>{ocfg['thread_id']}</code>, "
                    f"delay={ocfg.get('delay', 0)}"
                )
        else:
            lines.append(f"├ Чат: <code>{cfg.get('chat_id')}</code>")
            lines.append(f"├ Тред: <code>{cfg.get('thread_id')}</code>")
            lines.append(f"└ Delay: {cfg.get('delay', 0)} сек")
        lines.append("")

    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(Command("remove_hashtag"))
async def cmd_remove_hashtag(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Нет прав.")
        return

    parts = message.text.split()
    if len(parts) != 2 or not parts[1].startswith("#"):
        await message.answer(CMD_REMOVE_HASHTAG_USAGE, parse_mode="HTML")
        return

    hashtag = parts[1]
    if await config_manager.remove_hashtag(hashtag):
        await message.answer(f"✅ Хештег <b>{hashtag}</b> удалён.", parse_mode="HTML")
    else:
        await message.answer(f"❌ Хештег <b>{hashtag}</b> не найден.", parse_mode="HTML")


# ═════════════════════════════════════════════════════════════════════════════
# Утилиты
# ═════════════════════════════════════════════════════════════════════════════

@router.message(Command("get_thread_id"))
async def cmd_get_thread_id(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Нет прав.")
        return

    chat_id = message.chat.id
    chat_type = message.chat.type
    chat_title = message.chat.title or "Личный чат"
    thread_id = message.message_thread_id if message.is_topic_message else None

    resp = (
        f"<b>📊 Текущий чат:</b>\n\n"
        f"<b>Chat ID:</b> <code>{chat_id}</code>\n"
        f"<b>Название:</b> {chat_title}\n"
        f"<b>Тип:</b> {chat_type}\n"
    )
    if thread_id:
        resp += (
            f"\n<b>📌 Thread ID:</b> <code>{thread_id}</code>\n\n"
            f"💡 Для хештега:\n"
            f"<code>/add_hashtag #тег {chat_id} {thread_id}</code>\n\n"
            f"💡 Для keyword-правила:\n"
            f"<code>source={chat_id} sthread={thread_id}</code>"
        )
    elif chat_type in ("group", "supergroup"):
        resp += "\n<i>ℹ️ Не топик. Вызовите команду внутри нужного топика.</i>"
    else:
        resp += "\n<i>ℹ️ Личный чат или канал.</i>"

    await message.reply(resp, parse_mode="HTML")


# ═════════════════════════════════════════════════════════════════════════════
# Управление keyword_forwards
# ═════════════════════════════════════════════════════════════════════════════

@router.message(Command("add_keyword"))
async def cmd_add_keyword(message: Message):
    """
    Форматы:
      mode=keyword:
        /add_keyword source=CHAT_ID sthread=ID keyword=паттерн
                     target=CHAT_ID [tthread=ID] [prev=yes/no]

      mode=all:
        /add_keyword source=CHAT_ID sthread=ID
                     target=CHAT_ID [tthread=ID] mode=all
    """
    if not is_admin(message.from_user.id):
        await message.answer("❌ Нет прав.")
        return

    raw = message.text.partition(" ")[2].strip()
    if not raw:
        await message.answer(CMD_ADD_KEYWORD_USAGE, parse_mode="HTML")
        return

    kw = _parse_kwargs(raw)

    # Обязательные для всех режимов
    missing = [f for f in ("source", "sthread", "target") if f not in kw]
    if missing:
        await message.answer(
            f"❌ Не хватает параметров: <b>{', '.join(missing)}</b>\n\n"
            + CMD_ADD_KEYWORD_USAGE,
            parse_mode="HTML",
        )
        return

    try:
        source_chat_id  = int(kw["source"])
        source_thread_id = int(kw["sthread"])
        target_chat_id  = int(kw["target"])
        target_thread_id = int(kw["tthread"]) if "tthread" in kw else None
        mode = kw.get("mode", "keyword").lower()
    except ValueError as e:
        await message.answer(f"❌ Ошибка значения: {e}")
        return

    if mode not in ("all", "keyword"):
        await message.answer("❌ mode должен быть <b>all</b> или <b>keyword</b>.", parse_mode="HTML")
        return

    # Для mode=keyword keyword обязателен
    keyword_pattern = kw.get("keyword")
    if mode == "keyword" and not keyword_pattern:
        await message.answer(
            "❌ Для mode=keyword необходимо указать <b>keyword=паттерн</b>.",
            parse_mode="HTML",
        )
        return

    forward_previous = kw.get("prev", "yes").lower() not in ("no", "false", "0")

    await config_manager.add_keyword_forward(
        source_chat_id=source_chat_id,
        source_thread_id=source_thread_id,
        mode=mode,
        keyword=keyword_pattern,
        target_chat_id=target_chat_id,
        target_thread_id=target_thread_id,
        forward_previous=forward_previous,
    )

    lines = [
        "✅ <b>Правило добавлено!</b>\n",
        f"Режим: <b>{mode}</b>",
        f"Источник: <code>{source_chat_id}</code>, тред <code>{source_thread_id}</code>",
        f"Назначение: <code>{target_chat_id}</code>"
        + (f", тред <code>{target_thread_id}</code>" if target_thread_id else ""),
    ]
    if mode == "keyword":
        lines.append(f"Паттерн: <b>{keyword_pattern}</b>")
        lines.append(f"Prev media: {'✅' if forward_previous else '❌'}")

    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(Command("list_keywords"))
async def cmd_list_keywords(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Нет прав.")
        return

    kf_list = config_manager.list_keyword_forwards()
    if not kf_list:
        await message.answer("📝 Нет правил для ключевых слов.")
        return

    lines = ["<b>📋 Keyword-правила:</b>\n"]
    for i, item in enumerate(kf_list, 1):
        mode        = item.get("mode", "keyword")
        src         = item.get("source_chat_id")
        src_thread  = item.get("source_thread_id")
        dst         = item.get("target_chat_id")
        dst_thread  = item.get("target_thread_id")
        kw          = item.get("keyword")
        prev        = "✅" if item.get("forward_previous", True) else "❌"

        src_str = f"<code>{src}</code>" + (f" / тред <code>{src_thread}</code>" if src_thread else "")
        dst_str = f"<code>{dst}</code>" + (f" / тред <code>{dst_thread}</code>" if dst_thread else "")

        lines.append(f"<b>{i}. [{mode}]</b>")
        lines.append(f"  Источник: {src_str}")
        lines.append(f"  Цель:     {dst_str}")
        if mode == "keyword":
            lines.append(f"  Паттерн:  <b>{kw}</b>")
            lines.append(f"  Prev media: {prev}")
        lines.append("")

    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(Command("remove_keyword"))
async def cmd_remove_keyword(message: Message):
    """
    /remove_keyword source=CHAT_ID sthread=ID [keyword=паттерн]
    Для mode=all keyword не нужен.
    """
    if not is_admin(message.from_user.id):
        await message.answer("❌ Нет прав.")
        return

    raw = message.text.partition(" ")[2].strip()
    kw = _parse_kwargs(raw)

    if "source" not in kw or "sthread" not in kw:
        await message.answer(CMD_REMOVE_KEYWORD_USAGE, parse_mode="HTML")
        return

    try:
        source_chat_id   = int(kw["source"])
        source_thread_id = int(kw["sthread"])
    except ValueError:
        await message.answer("❌ source и sthread должны быть числами.")
        return

    keyword_pattern = kw.get("keyword")

    if await config_manager.remove_keyword_forward(
        source_chat_id=source_chat_id,
        source_thread_id=source_thread_id,
        keyword=keyword_pattern,
    ):
        label = f"паттерн <b>{keyword_pattern}</b>" if keyword_pattern else "mode=all"
        await message.answer(
            f"✅ Правило удалено ({label}, тред <code>{source_thread_id}</code>).",
            parse_mode="HTML",
        )
    else:
        await message.answer("❌ Правило не найдено.")