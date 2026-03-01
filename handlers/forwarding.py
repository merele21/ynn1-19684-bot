import asyncio
from typing import Optional, Dict, Any
from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from config import SOURCE_CHAT_ID, config_manager
from utils import extract_hashtags, remove_hashtag_from_text
from handlers.fsm import ForwardingStates, create_type_selection_keyboard

router = Router()

# Словарь для хранения сообщений, ожидающих пересылки с задержкой
pending_forwards: Dict[int, Dict[str, Any]] = {}


async def handle_message_with_delay(
    message: Message,
    hashtag: str,
    target_chat_id: int,
    target_thread_id: int,
    delay: int
):
    """
    Обработка сообщения с задержкой для сбора медиагруппы
    
    Args:
        message: Сообщение Telegram
        hashtag: Хештег для удаления
        target_chat_id: ID чата назначения
        target_thread_id: ID треда
        delay: Задержка в секундах
    """
    user_id = message.from_user.id
    
    # Сохраняем первое сообщение
    if user_id not in pending_forwards:
        pending_forwards[user_id] = {
            "messages": [],
            "hashtag": hashtag,
            "target_chat_id": target_chat_id,
            "target_thread_id": target_thread_id,
            "delay": delay,
            "timer_task": None
        }
    
    # Добавляем сообщение в очередь
    message_data = {
        "photo": message.photo[-1].file_id if message.photo else None,
        "text": message.text or message.caption,
        "message": message
    }
    pending_forwards[user_id]["messages"].append(message_data)
    
    # Отменяем предыдущий таймер, если он был
    if pending_forwards[user_id]["timer_task"]:
        pending_forwards[user_id]["timer_task"].cancel()
    
    # Создаём новый таймер
    async def delayed_forward():
        await asyncio.sleep(delay)
        await perform_delayed_forwarding(user_id, message.bot)
    
    pending_forwards[user_id]["timer_task"] = asyncio.create_task(delayed_forward())


async def perform_delayed_forwarding(user_id: int, bot):
    """Выполнить отложенную пересылку"""
    if user_id not in pending_forwards:
        return
    
    forward_data = pending_forwards[user_id]
    messages = forward_data["messages"]
    hashtag = forward_data["hashtag"]
    target_chat_id = forward_data["target_chat_id"]
    target_thread_id = forward_data["target_thread_id"]
    
    try:
        for idx, msg_data in enumerate(messages):
            text = msg_data.get("text", "")
            
            # Удаляем хештег только из первого сообщения
            if idx == 0 and text:
                text = remove_hashtag_from_text(text, hashtag)
            
            # Пересылаем сообщение
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
            
            # Небольшая задержка между сообщениями
            if idx < len(messages) - 1:
                await asyncio.sleep(0.5)
        
        print(f"✅ Переслано {len(messages)} сообщений для пользователя {user_id}")
    
    except Exception as e:
        print(f"❌ Ошибка при пересылке для пользователя {user_id}: {str(e)}")
    
    finally:
        # Очищаем данные
        del pending_forwards[user_id]


async def forward_simple_message(
    message: Message,
    hashtag: str,
    target_chat_id: int,
    target_thread_id: int
):
    """
    Простая пересылка сообщения без задержки
    
    Args:
        message: Сообщение Telegram
        hashtag: Хештег для удаления
        target_chat_id: ID чата назначения
        target_thread_id: ID треда
    """
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
        
        print(f"✅ Сообщение переслано: {hashtag} -> {target_chat_id}/{target_thread_id}")
    
    except Exception as e:
        print(f"❌ Ошибка при пересылке: {str(e)}")


@router.message(F.chat.id == SOURCE_CHAT_ID)
async def handle_source_chat_message(message: Message, state: FSMContext):
    """
    Обработка сообщений из исходной группы
    """
    # Получаем текст сообщения
    text = message.text or message.caption
    
    if not text:
        # Если нет текста и нет хештега - игнорируем
        return
    
    # Извлекаем хештеги
    hashtags = extract_hashtags(text)
    
    if not hashtags:
        # Проверяем, не находимся ли мы в режиме ожидания дополнительных сообщений
        current_state = await state.get_state()
        if current_state == ForwardingStates.waiting_for_type_selection.state:
            data = await state.get_data()
            if data.get("waiting_for_more"):
                # Добавляем это сообщение к дополнительным
                additional = data.get("additional_messages", [])
                additional.append({
                    "photo": message.photo[-1].file_id if message.photo else None,
                    "text": text,
                    "message": message
                })
                await state.update_data(additional_messages=additional)
        return
    
    # Обрабатываем первый найденный хештег
    hashtag = hashtags[0]
    
    # Получаем конфигурацию для этого хештега
    hashtag_config = config_manager.get_hashtag_config(hashtag)
    
    if not hashtag_config:
        # Хештег не в whitelist - игнорируем
        print(f"⚠️ Хештег {hashtag} не найден в конфигурации")
        return
    
    # Проверяем, нужен ли FSM для этого хештега
    if hashtag_config.get("needs_fsm"):
        # Сохраняем данные сообщения
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
        
        # Отправляем клавиатуру с выбором типа
        await message.answer(
            f"🤔 Выберите тип пересылки для хештега <b>{hashtag}</b>:",
            reply_markup=create_type_selection_keyboard(hashtag),
            parse_mode="HTML"
        )
    else:
        # Обычная пересылка без FSM
        target_chat_id = hashtag_config["chat_id"]
        target_thread_id = hashtag_config["thread_id"]
        delay = hashtag_config.get("delay", 0)
        
        if delay > 0:
            # Пересылка с задержкой (для медиагрупп)
            await handle_message_with_delay(
                message=message,
                hashtag=hashtag,
                target_chat_id=target_chat_id,
                target_thread_id=target_thread_id,
                delay=delay
            )
        else:
            # Простая пересылка без задержки
            await forward_simple_message(
                message=message,
                hashtag=hashtag,
                target_chat_id=target_chat_id,
                target_thread_id=target_thread_id
            )
