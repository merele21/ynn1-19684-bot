import os
import json
import logging
import aiofiles
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# Переменные окружения
# ─────────────────────────────────────────────

BOT_TOKEN = os.getenv("BOT_TOKEN")

_source_chat_raw = os.getenv("SOURCE_CHAT_ID", "")
if not _source_chat_raw:
    logger.warning("⚠️ SOURCE_CHAT_ID не задан в .env — пересылка из исходной группы работать не будет")
    SOURCE_CHAT_ID = 0
else:
    try:
        SOURCE_CHAT_ID = int(_source_chat_raw)
    except ValueError:
        logger.error(f"❌ SOURCE_CHAT_ID '{_source_chat_raw}' не является числом")
        SOURCE_CHAT_ID = 0

ADMIN_IDS = [
    int(id_.strip())
    for id_ in os.getenv("ADMIN_IDS", "").split(",")
    if id_.strip().lstrip("-").isdigit()
]

CONFIG_FILE = "config.json"
MAX_DELAY = 120  # секунд


class ConfigManager:
    """Менеджер для работы с конфигурацией хештегов"""

    def __init__(self, config_file: str = CONFIG_FILE):
        self.config_file = config_file
        self.config: Dict[str, Any] = {}

    async def load_config(self) -> Dict[str, Any]:
        """Загрузить конфигурацию из файла"""
        try:
            async with aiofiles.open(self.config_file, 'r', encoding='utf-8') as f:
                content = await f.read()
                self.config = json.loads(content)
                return self.config
        except FileNotFoundError:
            self.config = {"hashtags": {}, "keyword_forwards": []}
            await self.save_config()
            return self.config
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка парсинга JSON: {e}")
            self.config = {"hashtags": {}, "keyword_forwards": []}
            return self.config

    async def save_config(self) -> None:
        """Сохранить конфигурацию в файл"""
        async with aiofiles.open(self.config_file, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(self.config, ensure_ascii=False, indent=2))

    def get_hashtag_config(self, hashtag: str) -> Optional[Dict[str, Any]]:
        """Получить конфигурацию для конкретного хештега"""
        return self.config.get("hashtags", {}).get(hashtag)

    async def add_hashtag(
        self,
        hashtag: str,
        chat_id: int,
        thread_id: int,
        delay: int = 0,
        needs_fsm: bool = False,
        description: str = ""
    ) -> bool:
        """Добавить новый хештег в конфигурацию"""
        # Валидация delay
        delay = max(0, min(delay, MAX_DELAY))

        if "hashtags" not in self.config:
            self.config["hashtags"] = {}

        self.config["hashtags"][hashtag] = {
            "needs_fsm": needs_fsm,
            "description": description,
            "chat_id": chat_id,
            "thread_id": thread_id,
            "delay": delay
        }

        await self.save_config()
        return True

    async def remove_hashtag(self, hashtag: str) -> bool:
        """Удалить хештег из конфигурации"""
        if hashtag in self.config.get("hashtags", {}):
            del self.config["hashtags"][hashtag]
            await self.save_config()
            return True
        return False

    def list_hashtags(self) -> Dict[str, Any]:
        """Получить список всех хештегов"""
        return self.config.get("hashtags", {})

    # ─────────────────────────────────────────────
    # Методы для keyword_forwards
    # ─────────────────────────────────────────────

    def list_keyword_forwards(self) -> List[Dict[str, Any]]:
        """Получить список всех конфигов keyword_forwards"""
        return self.config.get("keyword_forwards", [])

    async def add_keyword_forward(
        self,
        source_chat_id: int,
        keyword: str,
        target_chat_id: int,
        target_thread_id: Optional[int] = None,
        forward_previous: bool = True
    ) -> bool:
        """
        Добавить правило пересылки по ключевому слову.

        Args:
            source_chat_id:    ID чата-источника (другая супергруппа)
            keyword:           ключевое слово-триггер
            target_chat_id:    куда пересылать
            target_thread_id:  тред назначения (None = без треда)
            forward_previous:  пересылать ли предыдущее сообщение
        """
        if "keyword_forwards" not in self.config:
            self.config["keyword_forwards"] = []

        # Избегаем дублей (same source + keyword)
        for item in self.config["keyword_forwards"]:
            if (
                item.get("source_chat_id") == source_chat_id
                and item.get("keyword", "").lower() == keyword.lower()
            ):
                # Обновляем существующий
                item.update({
                    "target_chat_id": target_chat_id,
                    "target_thread_id": target_thread_id,
                    "forward_previous": forward_previous,
                })
                await self.save_config()
                return True

        self.config["keyword_forwards"].append({
            "source_chat_id": source_chat_id,
            "keyword": keyword.lower(),
            "target_chat_id": target_chat_id,
            "target_thread_id": target_thread_id,
            "forward_previous": forward_previous,
        })
        await self.save_config()
        return True

    async def remove_keyword_forward(self, source_chat_id: int, keyword: str) -> bool:
        """Удалить правило пересылки по ключевому слову"""
        kf = self.config.get("keyword_forwards", [])
        new_kf = [
            item for item in kf
            if not (
                item.get("source_chat_id") == source_chat_id
                and item.get("keyword", "").lower() == keyword.lower()
            )
        ]
        if len(new_kf) == len(kf):
            return False
        self.config["keyword_forwards"] = new_kf
        await self.save_config()
        return True


# Глобальный экземпляр
config_manager = ConfigManager()