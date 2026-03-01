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
    logger.warning("⚠️ SOURCE_CHAT_ID не задан в .env")
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
    """Менеджер конфигурации"""

    def __init__(self, config_file: str = CONFIG_FILE):
        self.config_file = config_file
        self.config: Dict[str, Any] = {}

    async def load_config(self) -> Dict[str, Any]:
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
        async with aiofiles.open(self.config_file, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(self.config, ensure_ascii=False, indent=2))

    # ── Хештеги ───────────────────────────────────────────────────────────────

    def get_hashtag_config(self, hashtag: str) -> Optional[Dict[str, Any]]:
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
        if hashtag in self.config.get("hashtags", {}):
            del self.config["hashtags"][hashtag]
            await self.save_config()
            return True
        return False

    def list_hashtags(self) -> Dict[str, Any]:
        return self.config.get("hashtags", {})

    # ── Keyword forwards ──────────────────────────────────────────────────────
    #
    # Схема одной записи:
    # {
    #   "source_chat_id":   int,           # супергруппа-источник
    #   "source_thread_id": int | null,    # тред-источник (null = любой тред)
    #   "mode":             "all"|"keyword",
    #   "keyword":          str | null,    # паттерн; null для mode=all
    #   "target_chat_id":   int,
    #   "target_thread_id": int | null,
    #   "forward_previous": bool           # только для mode=keyword
    # }
    # ─────────────────────────────────────────────────────────────────────────

    def list_keyword_forwards(self) -> List[Dict[str, Any]]:
        return self.config.get("keyword_forwards", [])

    def _kf_key(self, item: Dict[str, Any]) -> tuple:
        """Составной уникальный ключ для записи keyword_forward"""
        return (
            item.get("source_chat_id"),
            item.get("source_thread_id"),
            item.get("keyword", ""),
        )

    async def add_keyword_forward(
        self,
        source_chat_id: int,
        source_thread_id: Optional[int],
        mode: str,                          # "all" | "keyword"
        target_chat_id: int,
        target_thread_id: Optional[int] = None,
        keyword: Optional[str] = None,
        forward_previous: bool = True,
    ) -> bool:
        if "keyword_forwards" not in self.config:
            self.config["keyword_forwards"] = []

        new_record: Dict[str, Any] = {
            "source_chat_id":   source_chat_id,
            "source_thread_id": source_thread_id,
            "mode":             mode,
            "keyword":          keyword,
            "target_chat_id":   target_chat_id,
            "target_thread_id": target_thread_id,
            "forward_previous": forward_previous,
        }
        new_key = self._kf_key(new_record)

        for i, item in enumerate(self.config["keyword_forwards"]):
            if self._kf_key(item) == new_key:
                self.config["keyword_forwards"][i] = new_record
                await self.save_config()
                return True

        self.config["keyword_forwards"].append(new_record)
        await self.save_config()
        return True

    async def remove_keyword_forward(
        self,
        source_chat_id: int,
        source_thread_id: Optional[int],
        keyword: Optional[str] = None,
    ) -> bool:
        kf = self.config.get("keyword_forwards", [])
        new_kf = []
        removed = False
        for item in kf:
            match_source = item.get("source_chat_id") == source_chat_id
            match_thread = item.get("source_thread_id") == source_thread_id
            match_kw = (keyword is None) or (
                (item.get("keyword") or "").lower() == keyword.lower()
            )
            if match_source and match_thread and match_kw:
                removed = True
            else:
                new_kf.append(item)
        if removed:
            self.config["keyword_forwards"] = new_kf
            await self.save_config()
        return removed


# Глобальный экземпляр
config_manager = ConfigManager()