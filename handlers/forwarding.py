"""
forwarding.py

Два независимых блока пересылки:

БЛОК 1 — SOURCE_CHAT_ID + хештеги
БЛОК 2 — Другие супергруппы + keyword_forwards

  mode=all     — пересылать ВСЕ сообщения из треда-источника в тред-цель.
  mode=keyword — пересылать только если:
                   1. Текст содержит keyword-паттерн.
                   2. Предыдущее сообщение (prev) является медиа
                      (фото / видео / аудио). Если prev — не медиа,
                      триггер игнорируется.
                 Порядок пересылки: сначала prev, затем триггер.
"""

import asyncio
import logging
import re
from typing import Optional, Dict, Any, List, Tuple

from aiogram import Router, F
from aiogram.types import Message, MessageEntity
from aiogram.fsm.context import FSMContext

from config import SOURCE_CHAT_ID, config_manager
from utils import extract_hashtags, remove_hashtag_from_text
from handlers.fsm import ForwardingStates, create_type_selection_keyboard

router = Router()
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Хранилища
# ─────────────────────────────────────────────────────────────────────────────

# Ожидающие пересылки с задержкой (ключ: "chat_id:user_id")
pending_forwards: Dict[str, Dict[str, Any]] = {}

# Последнее сообщение per (chat_id, thread_id) для keyword mode=keyword
# Ключ: (chat_id, thread_id | None)
last_messages: Dict[Tuple[int, Optional[int]], Message] = {}


# ═════════════════════════════════════════════════════════════════════════════
# БЛОК 1: SOURCE_CHAT_ID — пересылка по хештегам
# ═════════════════════════════════════════════════════════════════════════════

async def handle_message_with_delay(
    message: Message,
    hashtag: str,
    target_chat_id: int,
    target_thread_id: int,
    delay: int,
):
    """Пересылка с задержкой для медиагрупп"""
    key = f"{message.chat.id}:{message.from_user.id}"

    if key not in pending_forwards:
        pending_forwards[key] = {
            "messages": [],
            "hashtag": hashtag,
            "target_chat_id": target_chat_id,
            "target_thread_id": target_thread_id,
            "delay": delay,
            "timer_task": None,
        }

    pending_forwards[key]["messages"].append({
        "photo": message.photo[-1].file_id if message.photo else None,
        "text": message.text or message.caption,
    })

    if pending_forwards[key]["timer_task"]:
        pending_forwards[key]["timer_task"].cancel()

    async def _run():
        await asyncio.sleep(delay)
        await _perform_delayed_forwarding(key, message.bot)

    pending_forwards[key]["timer_task"] = asyncio.create_task(_run())


async def _perform_delayed_forwarding(key: str, bot) -> None:
    if key not in pending_forwards:
        return
    fd = pending_forwards[key]
    msgs, hashtag = fd["messages"], fd["hashtag"]
    target_chat_id, target_thread_id = fd["target_chat_id"], fd["target_thread_id"]
    try:
        for idx, md in enumerate(msgs):
            text = md.get("text", "")
            if idx == 0 and text:
                text = remove_hashtag_from_text(text, hashtag)
            if md.get("photo"):
                await bot.send_photo(
                    chat_id=target_chat_id,
                    photo=md["photo"],
                    caption=text or None,
                    message_thread_id=target_thread_id,
                )
            elif text:
                await bot.send_message(
                    chat_id=target_chat_id,
                    text=text,
                    message_thread_id=target_thread_id,
                )
            if idx < len(msgs) - 1:
                await asyncio.sleep(0.5)
        logger.info(f"✅ Delayed forward: {len(msgs)} msgs [{key}]")
    except Exception as e:
        logger.error(f"❌ Delayed forward error [{key}]: {e}")
    finally:
        del pending_forwards[key]


# Хештеги, текст которых нужно отправлять как команду Telegram (bot_command entity)
_COMMAND_HASHTAGS = {"#регистер"}


async def forward_simple_message(
    message: Message,
    hashtag: str,
    target_chat_id: int,
    target_thread_id: int,
) -> None:
    """Простая мгновенная пересылка"""
    text = message.text or message.caption
    clean = remove_hashtag_from_text(text, hashtag) if text else None
    try:
        if message.photo:
            await message.bot.send_photo(
                chat_id=target_chat_id,
                photo=message.photo[-1].file_id,
                caption=clean,
                message_thread_id=target_thread_id,
            )

        # ── Специальная обработка: хештеги-команды ───────────────────────────
        # Для хештегов из _COMMAND_HASHTAGS текст вида "/register YNN1-19684"
        # отправляется с entity bot_command, чтобы целевой бот распознал команду.
        elif hashtag in _COMMAND_HASHTAGS and clean and clean.startswith("/"):
            cmd_text = clean.strip()
            cmd_part = cmd_text.split()[0]  # первое слово — сама команда
            await message.bot.send_message(
                chat_id=target_chat_id,
                text=cmd_text,
                message_thread_id=target_thread_id,
                entities=[
                    MessageEntity(
                        type="bot_command",
                        offset=0,
                        length=len(cmd_part),
                    )
                ],
            )
            logger.info(
                f"✅ Command forward: {hashtag} '{cmd_text}' "
                f"-> {target_chat_id}/{target_thread_id}"
            )

        # ── Обычная текстовая пересылка ───────────────────────────────────────
        elif clean:
            await message.bot.send_message(
                chat_id=target_chat_id,
                text=clean,
                message_thread_id=target_thread_id,
            )
            logger.info(f"✅ Simple forward: {hashtag} -> {target_chat_id}/{target_thread_id}")

    except Exception as e:
        logger.error(f"❌ Simple forward error: {e}")


@router.message(F.chat.id == SOURCE_CHAT_ID)
async def handle_source_chat_message(message: Message, state: FSMContext) -> None:
    """Обработка сообщений из SOURCE_CHAT_ID"""
    text = message.text or message.caption
    if not text:
        return

    hashtags = extract_hashtags(text)
    if not hashtags:
        return

    hashtag = hashtags[0]
    hashtag_config = config_manager.get_hashtag_config(hashtag)
    if not hashtag_config:
        logger.warning(f"⚠️ Хештег {hashtag} не в конфигурации")
        return

    if hashtag_config.get("needs_fsm"):
        message_data = {
            "photo": message.photo[-1].file_id if message.photo else None,
            "text": text,
            "message": message,
        }
        await state.set_state(ForwardingStates.waiting_for_type_selection)
        await state.update_data(
            hashtag=hashtag,
            message_data=message_data,
            additional_messages=[],
        )
        await message.answer(
            f"🤔 Выберите тип пересылки для хештега <b>{hashtag}</b>:",
            reply_markup=create_type_selection_keyboard(hashtag),
            parse_mode="HTML",
        )
    else:
        target_chat_id = hashtag_config["chat_id"]
        target_thread_id = hashtag_config["thread_id"]
        delay = hashtag_config.get("delay", 0)
        if delay > 0:
            await handle_message_with_delay(
                message=message,
                hashtag=hashtag,
                target_chat_id=target_chat_id,
                target_thread_id=target_thread_id,
                delay=delay,
            )
        else:
            await forward_simple_message(
                message=message,
                hashtag=hashtag,
                target_chat_id=target_chat_id,
                target_thread_id=target_thread_id,
            )


# ═════════════════════════════════════════════════════════════════════════════
# БЛОК 2: Keyword-forwards из других супергрупп
# ═════════════════════════════════════════════════════════════════════════════

# ── Regex-утилиты ─────────────────────────────────────────────────────────────

_pattern_cache: Dict[str, re.Pattern] = {}


def _keyword_to_regex(keyword: str) -> re.Pattern:
    """
    Компилирует пользовательский паттерн в регулярное выражение.

      • '*' внутри токена → .{0,5}  (до 5 любых символов)
      • Пробел между токенами → .{0,50}  (токены могут разделяться другими словами)
      • Регистр игнорируется
    """
    tokens = keyword.strip().split()
    parts = []
    for token in tokens:
        sub = [re.escape(p) for p in token.split("*")]
        parts.append(".{0,5}".join(sub))
    return re.compile(".{0,50}".join(parts), re.IGNORECASE | re.DOTALL)


def _get_pattern(keyword: str) -> re.Pattern:
    if keyword not in _pattern_cache:
        _pattern_cache[keyword] = _keyword_to_regex(keyword)
    return _pattern_cache[keyword]


# ── thread_id сообщения ───────────────────────────────────────────────────────

def _msg_thread(message: Message) -> Optional[int]:
    """
    Возвращает thread_id сообщения.

    ВАЖНО: НЕ используем is_topic_message — у медиасообщений (фото, видео)
    этот флаг может быть False даже внутри топика, хотя message_thread_id
    при этом корректно выставлен. Берём напрямую.
    """
    return message.message_thread_id  # None если не в топике


# ── Поиск конфигов ────────────────────────────────────────────────────────────

def _find_configs_for_message(message: Message) -> List[Dict[str, Any]]:
    """
    Найти все keyword-конфиги, применимые к данному сообщению.
    Совпадение: chat_id + source_thread_id (точное, без None-wildcard).
    """
    chat_id = message.chat.id
    thread_id = _msg_thread(message)

    logger.debug(
        f"[find_configs] chat={chat_id} thread={thread_id} "
        f"total_configs={len(config_manager.list_keyword_forwards())}"
    )

    result = []
    for cfg in config_manager.list_keyword_forwards():
        cfg_chat   = cfg.get("source_chat_id")
        cfg_thread = cfg.get("source_thread_id")

        if cfg_chat != chat_id:
            logger.debug(f"  skip: chat {cfg_chat} != {chat_id}")
            continue
        if cfg_thread != thread_id:
            logger.debug(f"  skip: thread {cfg_thread} != {thread_id}")
            continue

        logger.debug(f"  match: mode={cfg.get('mode')} keyword={cfg.get('keyword')!r}")
        result.append(cfg)

    return result


# ── Проверка prev на медиа ────────────────────────────────────────────────────

def _is_media(message: Optional[Message]) -> bool:
    """True, если сообщение содержит фото, видео или аудио"""
    if message is None:
        return False
    return bool(message.photo or message.video or message.audio)


# ── Универсальная пересылка ───────────────────────────────────────────────────

async def _forward_any(
    message: Message,
    target_chat_id: int,
    target_thread_id: Optional[int],
) -> None:
    """Переслать сообщение любого типа в целевой чат/тред"""
    kw: Dict[str, Any] = {"chat_id": target_chat_id}
    if target_thread_id:
        kw["message_thread_id"] = target_thread_id

    if message.photo:
        await message.bot.send_photo(
            photo=message.photo[-1].file_id,
            caption=message.caption,
            **kw,
        )
    elif message.video:
        await message.bot.send_video(
            video=message.video.file_id,
            caption=message.caption,
            **kw,
        )
    elif message.audio:
        await message.bot.send_audio(
            audio=message.audio.file_id,
            caption=message.caption,
            **kw,
        )
    elif message.document:
        await message.bot.send_document(
            document=message.document.file_id,
            caption=message.caption,
            **kw,
        )
    elif message.sticker:
        await message.forward(chat_id=target_chat_id)
    elif message.text:
        await message.bot.send_message(text=message.text, **kw)
    else:
        await message.forward(chat_id=target_chat_id)


# ── Основной обработчик для других чатов ─────────────────────────────────────

@router.message()
async def handle_keyword_source(message: Message, state: FSMContext) -> None:
    """
    Обработчик для всех чатов, кроме SOURCE_CHAT_ID.

      mode=all:     пересылать любое сообщение из треда-источника.
      mode=keyword: триггер по паттерну; prev обязан быть медиа, иначе игнор.
    """
    if message.chat.id == SOURCE_CHAT_ID:
        return

    chat_id   = message.chat.id
    thread_id = _msg_thread(message)
    text      = message.text or message.caption or ""

    # ── Подробное логирование каждого входящего сообщения ────────────────────
    msg_type = (
        "photo"    if message.photo    else
        "video"    if message.video    else
        "audio"    if message.audio    else
        "document" if message.document else
        "sticker"  if message.sticker  else
        "text"     if message.text     else
        "other"
    )
    logger.info(
        f"[kw] incoming: chat={chat_id} thread={thread_id} "
        f"type={msg_type} text={text[:60]!r}"
    )

    configs = _find_configs_for_message(message)
    if not configs:
        logger.info(f"[kw] no configs matched for chat={chat_id} thread={thread_id}")
        return

    prev_key = (chat_id, thread_id)
    triggered_as_keyword = False

    for cfg in configs:
        mode             = cfg.get("mode", "keyword")
        target_chat_id   = cfg["target_chat_id"]
        target_thread_id = cfg.get("target_thread_id")

        # ── mode=all ─────────────────────────────────────────────────────────
        if mode == "all":
            try:
                await _forward_any(message, target_chat_id, target_thread_id)
                logger.info(
                    f"[kw][all] ✅ {chat_id}/{thread_id} -> "
                    f"{target_chat_id}/{target_thread_id}"
                )
            except Exception as e:
                logger.error(f"[kw][all] ❌ forward error: {e}")
            continue

        # ── mode=keyword ──────────────────────────────────────────────────────
        keyword          = cfg.get("keyword") or ""
        forward_previous = cfg.get("forward_previous", True)

        if not keyword:
            logger.warning(f"[kw][keyword] пустой паттерн в конфиге, пропускаем")
            continue

        pattern_match = _get_pattern(keyword).search(text)
        logger.info(
            f"[kw][keyword] pattern={keyword!r} "
            f"text={text[:60]!r} match={bool(pattern_match)}"
        )

        if not pattern_match:
            # Не триггер — запомним как prev ниже
            continue

        # ── Нашли триггер ────────────────────────────────────────────────────
        triggered_as_keyword = True
        prev = last_messages.get(prev_key)

        logger.info(
            f"[kw][keyword] TRIGGER '{keyword}' | "
            f"forward_previous={forward_previous} | "
            f"prev={('media' if _is_media(prev) else 'not_media') if prev else 'None'}"
        )

        if forward_previous:
            if not _is_media(prev):
                logger.info(
                    f"[kw][keyword] IGNORED — prev не медиа "
                    f"(chat={chat_id} thread={thread_id})"
                )
                continue

            try:
                await _forward_any(prev, target_chat_id, target_thread_id)
                await asyncio.sleep(0.3)
                await _forward_any(message, target_chat_id, target_thread_id)
                logger.info(
                    f"[kw][keyword] ✅ '{keyword}' "
                    f"{chat_id}/{thread_id} -> {target_chat_id}/{target_thread_id}"
                )
            except Exception as e:
                logger.error(f"[kw][keyword] ❌ forward error: {e}")
        else:
            try:
                await _forward_any(message, target_chat_id, target_thread_id)
                logger.info(
                    f"[kw][keyword/no-prev] ✅ '{keyword}' "
                    f"{chat_id}/{thread_id} -> {target_chat_id}/{target_thread_id}"
                )
            except Exception as e:
                logger.error(f"[kw][keyword/no-prev] ❌ error: {e}")

    # Обновляем prev только если сообщение не было триггером keyword
    if not triggered_as_keyword:
        prev_before = last_messages.get(prev_key)
        last_messages[prev_key] = message
        logger.debug(
            f"[kw] prev updated: chat={chat_id} thread={thread_id} "
            f"type={msg_type} "
            f"(was {'None' if prev_before is None else prev_before.message_id})"
        )