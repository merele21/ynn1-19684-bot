"""
ynn1-bot: утилита для регистрации магазина через HTTP API rbot.
IMPORTANT: RBOT_API_TOKEN должен совпадать со значением в rbot/bot/internal_api.py
"""
import asyncio
import logging
import aiohttp

logger = logging.getLogger(__name__)

# URL внутреннего API rbot — оба бота на одной машине, localhost
RBOT_API_URL = "http://127.0.0.1:8001/internal/register"

# Должен совпадать с INTERNAL_API_TOKEN в rbot/bot/internal_api.py
RBOT_API_TOKEN = "show me love"


async def register_store_in_rbot(
    telegram_id: int,
    store_id: str = None,
    username: str = None,
    full_name: str = None
) -> dict:
    """
    Регистрирует бота/магазин в базе данных rbot через HTTP API.

    Args:
        telegram_id: Telegram ID который нужно зарегистрировать
                     (обычно это telegram_id самого ynn1-bot или конкретного магазина)
        store_id:    ID магазина, например "YNN1-19684", опционально
        username:    username в Telegram (без @), опционально
        full_name:   Полное имя, опционально

    Returns:
        dict с ключами:
            ok: bool — успех или нет
            user_id: int — внутренний ID в БД rbot (если ok=True)
            store_id: str — store_id который был сохранён
            created: bool — True если запись новая, False если уже существовала
            error: str — описание ошибки (если ok=False)

    Примеры:
        result = await register_store_in_rbot(
            telegram_id=bot.id,
            store_id="YNN1-19684",
            username="ynn1bot",
            full_name="YNN1 Bot"
        )
        if result["ok"]:
            print("Зарегистрирован!" if result["created"] else "Уже был зарегистрирован")
        else:
            print(f"Ошибка: {result['error']}")
    """
    payload = {
        "telegram_id": telegram_id,
        "store_id": store_id,
    }
    if username:
        payload["username"] = username
    if full_name:
        payload["full_name"] = full_name

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                RBOT_API_URL,
                json=payload,
                headers={"X-Internal-Token": RBOT_API_TOKEN},
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.content_type == "application/json":
                    result = await resp.json()
                else:
                    text = await resp.text()
                    result = {"ok": False, "error": f"Non-JSON response: {text[:200]}"}

                logger.info(
                    f"[rbot_api] register store_id={store_id} "
                    f"telegram_id={telegram_id} → {result}"
                )
                return result

    except aiohttp.ClientConnectorError:
        logger.error("[rbot_api] Cannot connect to rbot API (is rbot running?)")
        return {"ok": False, "error": "rbot API недоступен — убедись что rbot запущен"}

    except asyncio.TimeoutError:
        logger.error("[rbot_api] Timeout connecting to rbot API")
        return {"ok": False, "error": "Таймаут подключения к rbot API"}

    except Exception as e:
        logger.error(f"[rbot_api] Unexpected error: {e}", exc_info=True)
        return {"ok": False, "error": str(e)}


# ============================================================
# Пример использования в forwarding.py ynn1-bot:
# ============================================================
#
# from utils.rbot_api import register_store_in_rbot
#
# _COMMAND_HASHTAGS = {"#регистер"}
#
# async def forward_simple_message(message, hashtag, ...):
#     ...
#     if hashtag in _COMMAND_HASHTAGS:
#         # Парсим store_id из текста сообщения
#         # Пример: "#регистер YNN1-19684" → store_id = "YNN1-19684"
#         parts = message.text.split()
#         store_id = parts[1].upper() if len(parts) > 1 else None
#
#         if not store_id:
#             await message.answer("❌ Не указан store_id")
#             return
#
#         bot_info = await message.bot.get_me()
#         result = await register_store_in_rbot(
#             telegram_id=bot_info.id,
#             store_id=store_id,
#             username=bot_info.username,
#             full_name=bot_info.full_name
#         )
#
#         if result.get("ok"):
#             if result.get("created"):
#                 logger.info(f"✅ Store {store_id} registered in rbot DB")
#             else:
#                 logger.info(f"ℹ️ Store {store_id} already registered in rbot DB")
#         else:
#             logger.error(f"❌ Failed to register store: {result.get('error')}")
#     ...