"""
forwarding.py

Два независимых блока пересылки:

БЛОК 1 — SOURCE_CHAT_ID + хештеги
    Обрабатывает сообщения из SOURCE_CHAT_ID.
    Пересылка по хештегам, поддержка FSM и delay.

БЛОК 2 — Другие супергруппы + keyword_forwards
    Два режима:
      mode=all     — пересылать ВСЕ сообщения из конкретного треда-источника
                     в тред-цель без каких-либо условий.
      mode=keyword — пересылать только если:
                       1. Сообщение содержит keyword-паттерн.
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
from aiogram.types import Message
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

    Правила:
      • '*' внутри токена → .{0,5}  (до 5 любых символов)
      • Пробел между токенами → .{0,50}  (токены могут разделяться другими словами)
      • Регистр игнорируется

    Примеры:
      "итого"         → найдёт «Итого», «ИТОГО»
      "товар* дн*"    → найдёт «товары дня», «товаров за дня»
      "закрыт* смен*" → найдёт «закрытие смены», «закрыто всей смены»

    Важно: корень слова должен совпадать буквально.
    «дн*» найдёт «дня/дней/дни», но НЕ «день» (там корень «де»).
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


# ── Хелперы для поиска конфига ────────────────────────────────────────────────

def _msg_thread(message: Message) -> Optional[int]:
    """Вернуть thread_id сообщения (None если не в топике)"""
    return message.message_thread_id if message.is_topic_message else None


def _find_configs_for_message(message: Message) -> List[Dict[str, Any]]:
    """
    Найти все keyword-конфиги, которые применимы к данному сообщению.
    Учитывает chat_id + source_thread_id.
    Возвращает список, т.к. для одного чата/треда может быть несколько правил.
    """
    chat_id = message.chat.id
    thread_id = _msg_thread(message)
    result = []
    for cfg in config_manager.list_keyword_forwards():
        if cfg.get("source_chat_id") != chat_id:
            continue
        cfg_thread = cfg.get("source_thread_id")
        # cfg_thread=None означает «любой тред» (не рекомендуется, но допускается)
        if cfg_thread is not None and cfg_thread != thread_id:
            continue
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
        # sticker не поддерживает message_thread_id — форвардим нативно
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

    Для каждого подходящего конфига:

      mode=all:
        Пересылать любое сообщение из треда-источника в тред-цель.
        Не сохраняет prev (не нужно).

      mode=keyword:
        1. Каждое НЕ-триггерное сообщение сохраняется как prev для своего
           (chat_id, thread_id).
        2. Если текст сообщения совпадает с keyword-паттерном:
           a. Проверяем prev — если prev не медиа, триггер ИГНОРИРУЕТСЯ.
           b. Если prev — медиа: пересылаем prev, затем триггерное сообщение.
    """
    # SOURCE_CHAT_ID обрабатывается отдельным хендлером выше
    if message.chat.id == SOURCE_CHAT_ID:
        return

    configs = _find_configs_for_message(message)
    if not configs:
        return

    chat_id = message.chat.id
    thread_id = _msg_thread(message)
    prev_key = (chat_id, thread_id)
    text = message.text or message.caption or ""

    # Флаг: было ли сообщение обработано хотя бы одним mode=keyword триггером
    triggered_as_keyword = False

    for cfg in configs:
        mode = cfg.get("mode", "keyword")
        target_chat_id = cfg["target_chat_id"]
        target_thread_id = cfg.get("target_thread_id")

        # ── mode=all ────────────────────────────────────────────────────────
        if mode == "all":
            try:
                await _forward_any(message, target_chat_id, target_thread_id)
                logger.info(
                    f"✅ [all] {chat_id}/{thread_id} -> "
                    f"{target_chat_id}/{target_thread_id}"
                )
            except Exception as e:
                logger.error(f"❌ [all] forward error: {e}")
            continue  # к следующему конфигу

        # ── mode=keyword ─────────────────────────────────────────────────────
        keyword = cfg.get("keyword") or ""
        forward_previous = cfg.get("forward_previous", True)

        if not keyword or not _get_pattern(keyword).search(text):
            # Не триггер — просто сохраняем как prev
            # (сохраним после цикла, ниже)
            continue

        # Нашли триггер
        triggered_as_keyword = True

        if forward_previous:
            prev = last_messages.get(prev_key)

            # Если prev не медиа — игнорируем этот триггер
            if not _is_media(prev):
                logger.info(
                    f"⏭ [keyword] Триггер '{keyword}' в {chat_id}/{thread_id} "
                    f"проигнорирован: prev не медиа"
                )
                continue

            try:
                # 1. Пересылаем prev (медиа)
                await _forward_any(prev, target_chat_id, target_thread_id)
                await asyncio.sleep(0.3)
                # 2. Пересылаем само триггерное сообщение
                await _forward_any(message, target_chat_id, target_thread_id)
                logger.info(
                    f"✅ [keyword] '{keyword}' {chat_id}/{thread_id} -> "
                    f"{target_chat_id}/{target_thread_id}"
                )
            except Exception as e:
                logger.error(f"❌ [keyword] forward error: {e}")
        else:
            # prev не нужен — пересылаем только триггер
            try:
                await _forward_any(message, target_chat_id, target_thread_id)
                logger.info(
                    f"✅ [keyword/no-prev] '{keyword}' {chat_id}/{thread_id} -> "
                    f"{target_chat_id}/{target_thread_id}"
                )
            except Exception as e:
                logger.error(f"❌ [keyword/no-prev] error: {e}")

    # Обновляем prev только если сообщение НЕ было триггером
    # (триггерное сообщение не должно становиться prev для следующего)
    if not triggered_as_keyword:
        last_messages[prev_key] = message