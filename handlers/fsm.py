import asyncio
import logging
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from config import SOURCE_CHAT_ID, config_manager
from utils import remove_hashtag_from_text

router = Router()
logger = logging.getLogger(__name__)


class ForwardingStates(StatesGroup):
    """Состояния FSM для пересылки с выбором типа"""
    waiting_for_type_selection = State()
    # Single-mode: ожидаем фото + описание от пользователя
    waiting_for_single_photo = State()
    # Mediagroup-mode: ожидаем доп. фото в течение delay
    waiting_for_mediagroup = State()


# ─────────────────────────────────────────────
# Клавиатура выбора типа пересылки
# ─────────────────────────────────────────────

def create_type_selection_keyboard(hashtag: str) -> InlineKeyboardMarkup:
    """Создать клавиатуру для выбора типа пересылки"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📷 Одиночное фото",
                    callback_data="forward_type:single"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🖼 Медиагруппа (11+ фото)",
                    callback_data="forward_type:mediagroup"
                )
            ]
        ]
    )


# ─────────────────────────────────────────────
# Обработка нажатия кнопки выбора типа
# ─────────────────────────────────────────────

@router.callback_query(F.data.startswith("forward_type:"))
async def process_type_selection(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора типа пересылки (single/mediagroup)"""
    data = await state.get_data()
    forward_type = callback.data.split(":")[1]

    hashtag = data.get("hashtag")
    message_data = data.get("message_data")

    if not hashtag or not message_data:
        await callback.answer("❌ Ошибка: данные не найдены", show_alert=True)
        await state.clear()
        return

    hashtag_config = config_manager.get_hashtag_config(hashtag)

    if not hashtag_config or "options" not in hashtag_config:
        await callback.answer("❌ Конфигурация не найдена", show_alert=True)
        await state.clear()
        return

    type_config = hashtag_config["options"].get(forward_type)
    if not type_config:
        await callback.answer("❌ Конфигурация для этого типа не найдена", show_alert=True)
        await state.clear()
        return

    # ── SINGLE MODE ──────────────────────────────────────────────────────────
    if forward_type == "single":
        await state.update_data(
            forward_type=forward_type,
            target_chat_id=type_config["chat_id"],
            target_thread_id=type_config["thread_id"],
        )
        await state.set_state(ForwardingStates.waiting_for_single_photo)

        await callback.message.edit_text(
            "📷 <b>Одиночное фото</b>\n\n"
            "Пришлите фото <b>с описанием</b> (caption обязателен).\n"
            "Для отмены отправьте /cancel",
            parse_mode="HTML"
        )
        await callback.answer()
        return

    # ── MEDIAGROUP MODE ───────────────────────────────────────────────────────
    delay = type_config.get("delay", 0)
    target_chat_id = type_config["chat_id"]
    target_thread_id = type_config["thread_id"]

    await state.update_data(
        forward_type=forward_type,
        target_chat_id=target_chat_id,
        target_thread_id=target_thread_id,
        delay=delay,
        waiting_for_more=True,
        additional_messages=[]
    )
    await state.set_state(ForwardingStates.waiting_for_mediagroup)

    await callback.message.edit_text(
        f"✅ Тип выбран: <b>Медиагруппа</b>\n\n"
        f"⏳ Жду дополнительные фото в течение {delay} сек...",
        parse_mode="HTML"
    )
    await callback.answer()

    # Запускаем таймер в фоне — не блокируем хендлер
    asyncio.create_task(
        _delayed_mediagroup_forward(
            bot=callback.bot,
            chat_id=callback.message.chat.id,
            state=state,
            delay=delay
        )
    )


# ─────────────────────────────────────────────
# Single-mode: получаем фото + обязательный caption
# ─────────────────────────────────────────────

@router.message(
    ForwardingStates.waiting_for_single_photo,
    F.chat.id == SOURCE_CHAT_ID
)
async def handle_single_photo(message: Message, state: FSMContext):
    """
    Ожидаем фото с описанием в single-mode.
    Если нет caption — сообщаем об ошибке и прерываем FSM.
    """
    # Команда отмены
    if message.text and message.text.strip() == "/cancel":
        await state.clear()
        await message.answer("❌ Операция отменена.")
        return

    # Нет фото вообще
    if not message.photo:
        await state.clear()
        await message.answer(
            "❌ Ожидалось фото. Операция отменена.\n"
            "Начните заново с хештега."
        )
        return

    # Фото есть, но нет описания
    if not message.caption or not message.caption.strip():
        await state.clear()
        await message.answer(
            "❌ <b>Нет описания к фото.</b> Попробуйте ещё раз.\n\n"
            "Начните заново с хештега — пришлите фото <b>вместе с текстом</b>.",
            parse_mode="HTML"
        )
        return

    # Всё хорошо — пересылаем
    data = await state.get_data()
    target_chat_id = data["target_chat_id"]
    target_thread_id = data["target_thread_id"]
    hashtag = data["hashtag"]

    caption = remove_hashtag_from_text(message.caption, hashtag)

    try:
        await message.bot.send_photo(
            chat_id=target_chat_id,
            photo=message.photo[-1].file_id,
            caption=caption or None,
            message_thread_id=target_thread_id
        )
        await message.answer("✅ Фото с описанием переслано!")
        logger.info(f"Single forward: {hashtag} -> {target_chat_id}/{target_thread_id}")
    except Exception as e:
        await message.answer(f"❌ Ошибка при пересылке: {e}")
        logger.error(f"Single forward error: {e}")
    finally:
        await state.clear()


# ─────────────────────────────────────────────
# Mediagroup-mode: собираем доп. фото
# ─────────────────────────────────────────────

@router.message(
    ForwardingStates.waiting_for_mediagroup,
    F.chat.id == SOURCE_CHAT_ID
)
async def handle_mediagroup_additional(message: Message, state: FSMContext):
    """Собираем дополнительные фото во время ожидания медиагруппы"""
    data = await state.get_data()
    if not data.get("waiting_for_more"):
        return

    # Пропускаем команды
    if message.text and message.text.startswith("/"):
        return

    additional = data.get("additional_messages", [])
    additional.append({
        "photo": message.photo[-1].file_id if message.photo else None,
        "text": message.text or message.caption,
    })
    await state.update_data(additional_messages=additional)


async def _delayed_mediagroup_forward(bot, chat_id: int, state: FSMContext, delay: int):
    """Фоновая задача: ждём delay секунд, потом пересылаем всё собранное"""
    await asyncio.sleep(delay)

    data = await state.get_data()
    if not data:
        return  # FSM уже сброшен

    target_chat_id = data.get("target_chat_id")
    target_thread_id = data.get("target_thread_id")
    hashtag = data.get("hashtag")
    message_data = data.get("message_data")
    additional_messages = data.get("additional_messages", [])

    if not message_data:
        await state.clear()
        return

    text = message_data.get("text", "")
    clean_text = remove_hashtag_from_text(text, hashtag) if text else None

    sent = 0
    try:
        # Основное сообщение
        if message_data.get("photo"):
            await bot.send_photo(
                chat_id=target_chat_id,
                photo=message_data["photo"],
                caption=clean_text or None,
                message_thread_id=target_thread_id
            )
            sent += 1
        elif clean_text:
            await bot.send_message(
                chat_id=target_chat_id,
                text=clean_text,
                message_thread_id=target_thread_id
            )
            sent += 1

        # Дополнительные сообщения
        for add_msg in additional_messages:
            if add_msg.get("photo"):
                await bot.send_photo(
                    chat_id=target_chat_id,
                    photo=add_msg["photo"],
                    caption=add_msg.get("text") or None,
                    message_thread_id=target_thread_id
                )
                sent += 1
            elif add_msg.get("text"):
                await bot.send_message(
                    chat_id=target_chat_id,
                    text=add_msg["text"],
                    message_thread_id=target_thread_id
                )
                sent += 1
            await asyncio.sleep(0.3)

        await bot.send_message(
            chat_id=chat_id,
            text=f"✅ Медиагруппа переслана! Сообщений: {sent}"
        )
        logger.info(f"Mediagroup forward: {sent} messages -> {target_chat_id}/{target_thread_id}")

    except Exception as e:
        await bot.send_message(chat_id=chat_id, text=f"❌ Ошибка при пересылке: {e}")
        logger.error(f"Mediagroup forward error: {e}")
    finally:
        await state.clear()