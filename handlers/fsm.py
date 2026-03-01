from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from config import SOURCE_CHAT_ID, config_manager
from utils import remove_hashtag_from_text

router = Router()


class ForwardingStates(StatesGroup):
    """Состояния FSM для пересылки с выбором типа"""
    waiting_for_type_selection = State()


@router.callback_query(F.data.startswith("forward_type:"))
async def process_type_selection(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора типа пересылки (single/mediagroup)"""
    data = await state.get_data()
    
    # Извлекаем тип из callback_data
    forward_type = callback.data.split(":")[1]  # single или mediagroup
    
    # Получаем сохранённые данные
    hashtag = data.get("hashtag")
    message_data = data.get("message_data")
    
    if not hashtag or not message_data:
        await callback.answer("❌ Ошибка: данные не найдены", show_alert=True)
        await state.clear()
        return
    
    # Получаем конфигурацию хештега
    hashtag_config = config_manager.get_hashtag_config(hashtag)
    
    if not hashtag_config or "options" not in hashtag_config:
        await callback.answer("❌ Конфигурация не найдена", show_alert=True)
        await state.clear()
        return
    
    # Получаем конфигурацию для выбранного типа
    type_config = hashtag_config["options"].get(forward_type)
    
    if not type_config:
        await callback.answer("❌ Конфигурация для этого типа не найдена", show_alert=True)
        await state.clear()
        return
    
    target_chat_id = type_config["chat_id"]
    target_thread_id = type_config["thread_id"]
    delay = type_config.get("delay", 0)
    
    # Если есть задержка и это медиагруппа - сохраняем данные для отложенной пересылки
    if delay > 0 and forward_type == "mediagroup":
        await state.update_data(
            target_chat_id=target_chat_id,
            target_thread_id=target_thread_id,
            delay=delay,
            forward_type=forward_type,
            waiting_for_more=True
        )
        await callback.message.edit_text(
            f"✅ Тип выбран: <b>{forward_type}</b>\n\n"
            f"⏳ Ожидаю дополнительные фото в течение {delay} секунд...",
            parse_mode="HTML"
        )
        await callback.answer()
        
        # Запускаем таймер для пересылки
        import asyncio
        await asyncio.sleep(delay)
        
        # Проверяем, не отменили ли мы уже пересылку
        current_data = await state.get_data()
        if current_data.get("waiting_for_more"):
            await perform_forwarding(callback.message, state)
    else:
        # Пересылаем сразу
        await perform_forwarding_single(
            callback.message,
            message_data,
            target_chat_id,
            target_thread_id,
            hashtag
        )
        await callback.message.edit_text("✅ Сообщение переслано!")
        await callback.answer()
        await state.clear()


async def perform_forwarding_single(
    bot_message: Message,
    message_data: dict,
    target_chat_id: int,
    target_thread_id: int,
    hashtag: str
):
    """Пересылка одиночного сообщения"""
    original_message = message_data["message"]
    text = message_data.get("text", "")
    
    # Удаляем хештег из текста
    clean_text = remove_hashtag_from_text(text, hashtag) if text else None
    
    try:
        # Если есть фото
        if message_data.get("photo"):
            await bot_message.bot.send_photo(
                chat_id=target_chat_id,
                photo=message_data["photo"],
                caption=clean_text,
                message_thread_id=target_thread_id
            )
        # Если только текст
        elif clean_text:
            await bot_message.bot.send_message(
                chat_id=target_chat_id,
                text=clean_text,
                message_thread_id=target_thread_id
            )
    except Exception as e:
        await bot_message.answer(f"❌ Ошибка при пересылке: {str(e)}")


async def perform_forwarding(bot_message: Message, state: FSMContext):
    """Выполнить отложенную пересылку (с задержкой)"""
    data = await state.get_data()
    
    target_chat_id = data.get("target_chat_id")
    target_thread_id = data.get("target_thread_id")
    hashtag = data.get("hashtag")
    message_data = data.get("message_data")
    additional_messages = data.get("additional_messages", [])
    
    # Удаляем хештег из основного текста
    text = message_data.get("text", "")
    clean_text = remove_hashtag_from_text(text, hashtag) if text else None
    
    try:
        # Пересылаем основное сообщение
        if message_data.get("photo"):
            await bot_message.bot.send_photo(
                chat_id=target_chat_id,
                photo=message_data["photo"],
                caption=clean_text,
                message_thread_id=target_thread_id
            )
        
        # Пересылаем дополнительные сообщения (без хештега)
        for add_msg in additional_messages:
            if add_msg.get("photo"):
                await bot_message.bot.send_photo(
                    chat_id=target_chat_id,
                    photo=add_msg["photo"],
                    caption=add_msg.get("text"),
                    message_thread_id=target_thread_id
                )
            elif add_msg.get("text"):
                await bot_message.bot.send_message(
                    chat_id=target_chat_id,
                    text=add_msg["text"],
                    message_thread_id=target_thread_id
                )
        
        await bot_message.bot.send_message(
            chat_id=bot_message.chat.id,
            text=f"✅ Пересылка завершена! Переслано: {1 + len(additional_messages)} сообщений"
        )
    except Exception as e:
        await bot_message.bot.send_message(
            chat_id=bot_message.chat.id,
            text=f"❌ Ошибка при пересылке: {str(e)}"
        )
    finally:
        await state.clear()


def create_type_selection_keyboard(hashtag: str) -> InlineKeyboardMarkup:
    """Создать клавиатуру для выбора типа пересылки"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📷 Одиночное фото",
                    callback_data=f"forward_type:single"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🖼 Медиагруппа (11+ фото)",
                    callback_data=f"forward_type:mediagroup"
                )
            ]
        ]
    )
    return keyboard
