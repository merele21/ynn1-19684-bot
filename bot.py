import asyncio
import logging
from aiogram import Bot, Dispatcher, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, BotCommandScopeDefault

from config import BOT_TOKEN, ADMIN_IDS, config_manager
from commands import BOT_COMMANDS
from handlers import admin_router, forwarding_router, fsm_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
# Для отладки keyword-пересылки раскомментируйте строку ниже:
# logging.getLogger("handlers.forwarding").setLevel(logging.DEBUG)
logger = logging.getLogger(__name__)


async def setup_bot_commands(bot: Bot) -> None:
    """Зарегистрировать команды в меню '/' Telegram"""
    await bot.set_my_commands(commands=BOT_COMMANDS, scope=BotCommandScopeDefault())
    logger.info(f"✅ Зарегистрировано {len(BOT_COMMANDS)} команд в меню бота")


async def main() -> None:
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN не установлен!")
        return

    bot = Bot(token=BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # ── Глобальный /cancel — первый роутер ───────────────────────────────────
    cancel_router = Router()

    @cancel_router.message(Command("cancel"))
    async def global_cancel(message: Message, state: FSMContext) -> None:
        if message.from_user.id not in ADMIN_IDS:
            return
        if await state.get_state():
            await state.clear()
            await message.answer("❌ Операция отменена.")
        else:
            await message.answer("ℹ️ Нет активной операции.")

    dp.include_router(cancel_router)
    # ─────────────────────────────────────────────────────────────────────────

    dp.include_router(admin_router)
    dp.include_router(fsm_router)
    dp.include_router(forwarding_router)

    # Загрузка конфигурации
    logger.info("📥 Загрузка конфигурации...")
    await config_manager.load_config()
    logger.info(
        f"✅ Хештегов: {len(config_manager.list_hashtags())}, "
        f"keyword-правил: {len(config_manager.list_keyword_forwards())}"
    )

    # Регистрация команд в UI
    await setup_bot_commands(bot)

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