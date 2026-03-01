import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message

from config import BOT_TOKEN, config_manager
from handlers import admin_router, forwarding_router, fsm_router

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN не установлен!")
        return

    bot = Bot(token=BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # ── Глобальный /cancel — должен быть ПЕРВЫМ роутером ──────────────────
    from aiogram import Router
    from aiogram.fsm.context import FSMContext

    cancel_router = Router()

    @cancel_router.message(Command("cancel"))
    async def global_cancel(message: Message, state: FSMContext):
        from config import ADMIN_IDS
        if message.from_user.id not in ADMIN_IDS:
            return
        current = await state.get_state()
        if current:
            await state.clear()
            await message.answer("❌ Операция отменена.")
        else:
            await message.answer("ℹ️ Нет активной операции.")

    dp.include_router(cancel_router)
    # ──────────────────────────────────────────────────────────────────────

    dp.include_router(admin_router)
    dp.include_router(fsm_router)
    dp.include_router(forwarding_router)

    logger.info("📥 Загрузка конфигурации...")
    await config_manager.load_config()
    hashtags = config_manager.list_hashtags()
    kf = config_manager.list_keyword_forwards()
    logger.info(f"✅ Хештегов: {len(hashtags)}, правил keyword: {len(kf)}")

    logger.info("🤖 Бот запущен!")

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()
        logger.info("🛑 Бот остановлен")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("⚠️ Остановлен пользователем")