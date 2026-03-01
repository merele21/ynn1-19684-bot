import asyncio
import logging
from typing import Optional, Dict, Any, List
from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from config import SOURCE_CHAT_ID, config_manager
from utils import extract_hashtags, remove_hashtag_from_text
from handlers.fsm import ForwardingStates, create_type_selection_keyboard

router = Router()
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Хранилище для отложенных пересылок (ключ: chat_id + user_id для уникальности)
# ─────────────────────────────────────────────────────────────────────────────
pending_forwards: Dict[str, Dict[str, Any]] = {}

# ─────────────────────────────────────────────────────────────────────────────
# Хранилище последних сообщений по каждому чату (для пересылки "предыдущего")
# Ключ: chat_id, значение: последнее НЕ-триггерное сообщение
# ─────────────────────────────────────────────────────────────────────────────
last_messages: Dict[int, Message] = {}


# ═════════════════════════════════════════════════════════════════════════════
# БЛОК 1: Пересылка из SOURCE_CHAT_ID по хештегам (существующая логика)
# ═════════════════════════════════════════════════════════════════════════════

async def handle_message_with_delay(
    message: Message,
    hashtag: str,
    target_chat_id: int,
    target_thread_id: int,
    delay: int
):
    """Пересылка с задержкой для медиагрупп"""
    # Составной ключ чтобы разные пользователи не мешали друг другу
    key = f"{message.chat.id}:{message.from_user.id}"

    if key not in pending_forwards:
        pending_forwards[key] = {
            "messages": [],
            "hashtag": hashtag,
            "target_chat_id": target_chat_id,
            "target_thread_id": target_thread_id,
            "delay": delay,
            "timer_task": None
        }

    pending_forwards[key]["messages"].append({
        "photo": message.photo[-1].file_id if message.photo else None,
        "text": message.text or message.caption,
        "message": message
    })

    if pending_forwards[key]["timer_task"]:
        pending_forwards[key]["timer_task"].cancel()

    async def delayed_forward():
        await asyncio.sleep(delay)
        await perform_delayed_forwarding(key, message.bot)

    pending_forwards[key]["timer_task"] = asyncio.create_task(delayed_forward())


async def perform_delayed_forwarding(key: str, bot):
    """Выполнить отложенную пересылку"""
    if key not in pending_forwards:
        return

    forward_data = pending_forwards[key]
    messages = forward_data["messages"]
    hashtag = forward_data["hashtag"]
    target_chat_id = forward_data["target_chat_id"]
    target_thread_id = forward_data["target_thread_id"]

    try:
        for idx, msg_data in enumerate(messages):
            text = msg_data.get("text", "")
            if idx == 0 and text:
                text = remove_hashtag_from_text(text, hashtag)

            if msg_data.get("photo"):
                await bot.send_photo(
                    chat_id=target_chat_id,
                    photo=msg_data["photo"],
                    caption=text if text else None,
                    message_thread_id=target_thread_id
                )
            elif text:
                await bot.send_message(
                    chat_id=target_chat_id,
                    text=text,
                    message_thread_id=target_thread_id
                )

            if idx < len(messages) - 1:
                await asyncio.sleep(0.5)

        logger.info(f"✅ Delayed forward: {len(messages)} сообщений [{key}]")

    except Exception as e:
        logger.error(f"❌ Ошибка delayed forward [{key}]: {e}")
    finally:
        del pending_forwards[key]


async def forward_simple_message(
    message: Message,
    hashtag: str,
    target_chat_id: int,
    target_thread_id: int
):
    """Простая мгновенная пересылка"""
    text = message.text or message.caption
    clean_text = remove_hashtag_from_text(text, hashtag) if text else None

    try:
        if message.photo:
            await message.bot.send_photo(
                chat_id=target_chat_id,
                photo=message.photo[-1].file_id,
                caption=clean_text,
                message_thread_id=target_thread_id
            )
        elif clean_text:
            await message.bot.send_message(
                chat_id=target_chat_id,
                text=clean_text,
                message_thread_id=target_thread_id
            )

        logger.info(f"✅ Simple forward: {hashtag} -> {target_chat_id}/{target_thread_id}")

    except Exception as e:
        logger.error(f"❌ Ошибка simple forward: {e}")


@router.message(F.chat.id == SOURCE_CHAT_ID)
async def handle_source_chat_message(message: Message, state: FSMContext):
    """Обработка сообщений из исходной группы (SOURCE_CHAT_ID)"""
    text = message.text or message.caption

    if not text:
        return

    hashtags = extract_hashtags(text)

    if not hashtags:
        current_state = await state.get_state()
        if current_state == ForwardingStates.waiting_for_mediagroup.state:
            # Доп. сообщение для медиагруппы — обрабатывается в fsm.py
            pass
        return

    hashtag = hashtags[0]
    hashtag_config = config_manager.get_hashtag_config(hashtag)

    if not hashtag_config:
        logger.warning(f"⚠️ Хештег {hashtag} не найден в конфигурации")
        return

    if hashtag_config.get("needs_fsm"):
        message_data = {
            "photo": message.photo[-1].file_id if message.photo else None,
            "text": text,
            "message": message
        }

        await state.set_state(ForwardingStates.waiting_for_type_selection)
        await state.update_data(
            hashtag=hashtag,
            message_data=message_data,
            additional_messages=[]
        )

        await message.answer(
            f"🤔 Выберите тип пересылки для хештега <b>{hashtag}</b>:",
            reply_markup=create_type_selection_keyboard(hashtag),
            parse_mode="HTML"
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
                delay=delay
            )
        else:
            await forward_simple_message(
                message=message,
                hashtag=hashtag,
                target_chat_id=target_chat_id,
                target_thread_id=target_thread_id
            )


# ═════════════════════════════════════════════════════════════════════════════
# БЛОК 2: Пересылка из другой супергруппы по ключевому слову
#
# Конфиг хранится в config.json под ключом "keyword_forwards":
# {
#   "keyword_forwards": [
#     {
#       "source_chat_id": -100XXXXXXXXX,   // супергруппа-источник
#       "keyword": "итого",                 // триггер (без регистра)
#       "target_chat_id": -100YYYYYYYYY,
#       "target_thread_id": 123,
#       "forward_previous": true            // пересылать ли предыдущее сообщение
#     }
#   ]
# }
# ═════════════════════════════════════════════════════════════════════════════

def get_keyword_configs() -> List[Dict[str, Any]]:
    """Получить список конфигов ключевых слов из config.json"""
    return config_manager.config.get("keyword_forwards", [])


def find_keyword_config(chat_id: int, text: str) -> Optional[Dict[str, Any]]:
    """Найти подходящий конфиг по chat_id и тексту сообщения"""
    if not text:
        return None
    text_lower = text.lower()
    for cfg in get_keyword_configs():
        if cfg.get("source_chat_id") == chat_id:
            keyword = cfg.get("keyword", "").lower()
            if keyword and keyword in text_lower:
                return cfg
    return None


@router.message()
async def handle_keyword_source(message: Message, state: FSMContext):
    """
    Обработчик для супергрупп с ключевыми словами.
    Работает со ВСЕМИ чатами кроме SOURCE_CHAT_ID (тот уже перехвачен выше).

    Логика:
    1. Сохраняем каждое входящее сообщение как "предыдущее" для данного чата.
    2. Если сообщение содержит ключевое слово — пересылаем:
       - сначала предыдущее сообщение (если forward_previous=true),
       - затем само триггерное сообщение.
    """
    # Игнорируем SOURCE_CHAT_ID — он обрабатывается выше
    if message.chat.id == SOURCE_CHAT_ID:
        return

    text = message.text or message.caption or ""
    chat_id = message.chat.id

    keyword_cfg = find_keyword_config(chat_id, text)

    if keyword_cfg is None:
        # Не триггер — просто запоминаем как "предыдущее"
        last_messages[chat_id] = message
        return

    # ── Нашли триггер ────────────────────────────────────────────────────────
    target_chat_id = keyword_cfg["target_chat_id"]
    target_thread_id = keyword_cfg.get("target_thread_id")
    forward_previous = keyword_cfg.get("forward_previous", True)

    try:
        # 1. Пересылаем предыдущее сообщение (если есть и нужно)
        if forward_previous:
            prev = last_messages.get(chat_id)
            if prev and prev.message_id != message.message_id:
                await _forward_any_message(prev, target_chat_id, target_thread_id)
                await asyncio.sleep(0.3)

        # 2. Пересылаем само триггерное сообщение
        await _forward_any_message(message, target_chat_id, target_thread_id)

        logger.info(
            f"✅ Keyword forward: '{keyword_cfg['keyword']}' "
            f"из {chat_id} -> {target_chat_id}/{target_thread_id}"
        )

    except Exception as e:
        logger.error(f"❌ Ошибка keyword forward: {e}")

    # После триггера обновляем "предыдущее" тоже
    last_messages[chat_id] = message


async def _forward_any_message(
    message: Message,
    target_chat_id: int,
    target_thread_id: Optional[int]
):
    """
    Универсальная пересылка любого типа сообщения:
    фото, текст, документ, видео, стикер и т.д.
    """
    kwargs = {
        "chat_id": target_chat_id,
    }
    if target_thread_id:
        kwargs["message_thread_id"] = target_thread_id

    if message.photo:
        await message.bot.send_photo(
            photo=message.photo[-1].file_id,
            caption=message.caption,
            **kwargs
        )
    elif message.video:
        await message.bot.send_video(
            video=message.video.file_id,
            caption=message.caption,
            **kwargs
        )
    elif message.document:
        await message.bot.send_document(
            document=message.document.file_id,
            caption=message.caption,
            **kwargs
        )
    elif message.sticker:
        # sticker не поддерживает message_thread_id во всех версиях API,
        # поэтому пересылаем через forward_message
        await message.forward(chat_id=target_chat_id)
    elif message.text:
        await message.bot.send_message(
            text=message.text,
            **kwargs
        )
    else:
        # Всё остальное — пересылаем нативно
        await message.forward(chat_id=target_chat_id)