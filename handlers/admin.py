from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from config import ADMIN_IDS, config_manager

router = Router()


def is_admin(user_id: int) -> bool:
    """Проверка, является ли пользователь администратором"""
    return user_id in ADMIN_IDS


@router.message(Command("start"))
async def cmd_start(message: Message):
    """Команда /start"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к этому боту.")
        return
    
    await message.answer(
        "🤖 <b>Telegram Forwarder Bot</b>\n\n"
        "Доступные команды:\n"
        "/add_hashtag - Добавить новый хештег\n"
        "/list_hashtags - Список всех хештегов\n"
        "/remove_hashtag - Удалить хештег\n"
        "/get_thread_id - Получить Chat ID и Thread ID\n"
        "/help - Помощь",
        parse_mode="HTML"
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Команда /help"""
    if not is_admin(message.from_user.id):
        return
    
    help_text = """
<b>📖 Справка по командам</b>

<b>/add_hashtag</b>
Добавить новый хештег в конфигурацию
Формат: <code>/add_hashtag #хештег -100123456789 123 delay=10</code>
• #хештег - хештег для пересылки
• -100123456789 - ID чата назначения (Chat ID)
• 123 - ID треда (Thread ID)
• delay=10 (опционально) - задержка в секундах

<b>/list_hashtags</b>
Показать все настроенные хештеги

<b>/remove_hashtag</b>
Удалить хештег
Формат: <code>/remove_hashtag #хештег</code>

<b>/get_thread_id</b>
Получить Chat ID и Thread ID текущего чата/треда
• Вызовите команду в нужном чате/треде
• Бот покажет Chat ID и Thread ID (если это топик)
• Скопируйте значения для настройки хештега

<b>💡 Совет:</b>
Для получения Thread ID вызовите команду прямо в нужном топике!
"""
    await message.answer(help_text, parse_mode="HTML")


@router.message(Command("add_hashtag"))
async def cmd_add_hashtag(message: Message):
    """
    Команда для добавления нового хештега
    Формат: /add_hashtag #хештег -100123456789 123 delay=10
    """
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return
    
    try:
        parts = message.text.split()
        if len(parts) < 4:
            await message.answer(
                "❌ Неверный формат команды.\n\n"
                "Используйте:\n"
                "<code>/add_hashtag #хештег -100123456789 123 delay=10</code>\n\n"
                "где:\n"
                "• #хештег - хештег для пересылки\n"
                "• -100123456789 - ID чата назначения\n"
                "• 123 - ID треда\n"
                "• delay=10 (опционально) - задержка в секундах",
                parse_mode="HTML"
            )
            return
        
        hashtag = parts[1]
        chat_id = int(parts[2])
        thread_id = int(parts[3])
        delay = 0
        
        # Проверяем наличие параметра delay
        if len(parts) > 4 and parts[4].startswith("delay="):
            delay = int(parts[4].split("=")[1])
        
        # Проверяем формат хештега
        if not hashtag.startswith("#"):
            await message.answer("❌ Хештег должен начинаться с символа #")
            return
        
        # Добавляем хештег в конфигурацию
        await config_manager.add_hashtag(
            hashtag=hashtag,
            chat_id=chat_id,
            thread_id=thread_id,
            delay=delay,
            needs_fsm=False,
            description=f"Добавлено администратором {message.from_user.id}"
        )
        
        await message.answer(
            f"✅ Хештег <b>{hashtag}</b> успешно добавлен!\n\n"
            f"Чат: <code>{chat_id}</code>\n"
            f"Тред: <code>{thread_id}</code>\n"
            f"Задержка: {delay} сек",
            parse_mode="HTML"
        )
    
    except (ValueError, IndexError) as e:
        await message.answer(
            f"❌ Ошибка при обработке команды: {str(e)}\n\n"
            "Проверьте формат команды."
        )


@router.message(Command("list_hashtags"))
async def cmd_list_hashtags(message: Message):
    """Команда для просмотра всех хештегов"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return
    
    hashtags = config_manager.list_hashtags()
    
    if not hashtags:
        await message.answer("📝 Список хештегов пуст.")
        return
    
    response = "<b>📋 Список хештегов:</b>\n\n"
    
    for hashtag, config in hashtags.items():
        response += f"<b>{hashtag}</b>\n"
        
        if config.get("needs_fsm"):
            response += "├ FSM: ✅ (требует выбора типа)\n"
            if "options" in config:
                for option_type, option_config in config["options"].items():
                    response += f"├─ {option_type}:\n"
                    response += f"│  ├ Чат: <code>{option_config['chat_id']}</code>\n"
                    response += f"│  ├ Тред: <code>{option_config['thread_id']}</code>\n"
                    response += f"│  └ Delay: {option_config.get('delay', 0)} сек\n"
        else:
            response += f"├ Чат: <code>{config.get('chat_id')}</code>\n"
            response += f"├ Тред: <code>{config.get('thread_id')}</code>\n"
            response += f"└ Delay: {config.get('delay', 0)} сек\n"
        
        response += "\n"
    
    await message.answer(response, parse_mode="HTML")


@router.message(Command("remove_hashtag"))
async def cmd_remove_hashtag(message: Message):
    """
    Команда для удаления хештега
    Формат: /remove_hashtag #хештег
    """
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return
    
    try:
        parts = message.text.split()
        if len(parts) != 2:
            await message.answer(
                "❌ Неверный формат команды.\n\n"
                "Используйте: <code>/remove_hashtag #хештег</code>",
                parse_mode="HTML"
            )
            return
        
        hashtag = parts[1]
        
        if not hashtag.startswith("#"):
            await message.answer("❌ Хештег должен начинаться с символа #")
            return
        
        success = await config_manager.remove_hashtag(hashtag)
        
        if success:
            await message.answer(f"✅ Хештег <b>{hashtag}</b> успешно удалён!", parse_mode="HTML")
        else:
            await message.answer(f"❌ Хештег <b>{hashtag}</b> не найден в конфигурации.", parse_mode="HTML")
    
    except Exception as e:
        await message.answer(f"❌ Ошибка при удалении хештега: {str(e)}")


@router.message(Command("get_thread_id"))
async def cmd_get_thread_id(message: Message):
    """Команда для получения ID текущего чата и треда"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return
    
    # Получаем информацию о текущем чате
    chat_id = message.chat.id
    chat_type = message.chat.type
    chat_title = message.chat.title if message.chat.title else "Личный чат"
    
    # Получаем Thread ID если это топик
    thread_id = message.message_thread_id if message.is_topic_message else None
    
    response = f"<b>📊 Информация о текущем чате:</b>\n\n"
    response += f"<b>Chat ID:</b> <code>{chat_id}</code>\n"
    response += f"<b>Название:</b> {chat_title}\n"
    response += f"<b>Тип:</b> {chat_type}\n"
    
    if thread_id:
        response += f"\n<b>📌 Thread ID:</b> <code>{thread_id}</code>\n"
        response += f"\n💡 <i>Используйте эти значения при настройке хештега:</i>\n"
        response += f"<code>/add_hashtag #хештег {chat_id} {thread_id}</code>"
    else:
        if chat_type in ["group", "supergroup"]:
            response += f"\n<i>ℹ️ Это сообщение не из треда (топика)</i>\n"
            response += f"\n💡 <i>Для получения Thread ID вызовите команду внутри нужного топика</i>"
        else:
            response += f"\n<i>ℹ️ Это личный чат или канал</i>"
    
    await message.reply(response, parse_mode="HTML")

