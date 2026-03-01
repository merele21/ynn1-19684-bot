import os
import json
import aiofiles
from typing import Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

# Загрузка переменных окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")
SOURCE_CHAT_ID = int(os.getenv("SOURCE_CHAT_ID", "0"))
ADMIN_IDS = [int(id.strip()) for id in os.getenv("ADMIN_IDS", "").split(",") if id.strip()]

CONFIG_FILE = "config.json"


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
            self.config = {"hashtags": {}}
            await self.save_config()
            return self.config
        except json.JSONDecodeError as e:
            print(f"Ошибка парсинга JSON: {e}")
            self.config = {"hashtags": {}}
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
        """
        Добавить новый хештег в конфигурацию
        
        Args:
            hashtag: Хештег (с #)
            chat_id: ID чата назначения
            thread_id: ID треда
            delay: Задержка в секундах
            needs_fsm: Нужен ли FSM
            description: Описание хештега
        
        Returns:
            True если успешно добавлено
        """
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


# Глобальный экземпляр менеджера конфигурации
config_manager = ConfigManager()
