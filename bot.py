import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, config_manager
from handlers import admin_router, forwarding_router, fsm_router

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Главная функция для запуска бота"""
    
    # Проверка токена
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN не установлен! Проверьте .env файл")
        return
    
    # Инициализация бота и диспетчера
    bot = Bot(token=BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    # Загрузка конфигурации хештегов
    logger.info("📥 Загрузка конфигурации хештегов...")
    await config_manager.load_config()
    hashtags = config_manager.list_hashtags()
    logger.info(f"✅ Загружено {len(hashtags)} хештегов")
    
    # Регистрация роутеров
    dp.include_router(admin_router)
    dp.include_router(fsm_router)
    dp.include_router(forwarding_router)
    
    logger.info("🤖 Бот запущен!")
    
    try:
        # Запуск бота
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()
        logger.info("🛑 Бот остановлен")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("⚠️ Бот остановлен пользователем")
