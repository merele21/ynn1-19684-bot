# 📁 Структура проекта

```
telegram_forwarder_bot/
│
├── 📄 bot.py                          # Главный файл запуска бота
├── 📄 config.py                       # Менеджер конфигурации
├── 📄 config.json                     # Конфигурация хештегов (редактируемый)
├── 📄 .env                            # Переменные окружения (создать из .env.example)
├── 📄 .env.example                    # Пример файла окружения
├── 📄 requirements.txt                # Python зависимости
├── 📄 .gitignore                      # Git ignore правила
├── 🔧 run.sh                          # Скрипт быстрого запуска
├── 🧪 test_hashtag_parser.py         # Тесты для парсера хештегов
│
├── 📚 Документация
│   ├── README.md                      # Основная документация
│   ├── QUICKSTART.md                  # Быстрый старт
│   ├── USAGE_EXAMPLES.md              # Примеры использования
│   ├── FAQ.md                         # Частые вопросы
│   ├── CHANGELOG.md                   # История изменений
│   ├── PROJECT_STRUCTURE.md           # Этот файл
│   └── LICENSE                        # MIT лицензия
│
├── 📂 handlers/                       # Обработчики событий
│   ├── __init__.py                    # Инициализация модуля
│   ├── admin.py                       # Административные команды
│   ├── forwarding.py                  # Основная логика пересылки
│   └── fsm.py                         # FSM обработчики
│
├── 📂 utils/                          # Утилиты
│   ├── __init__.py                    # Инициализация модуля
│   └── hashtag_parser.py              # Парсинг хештегов
│
├── 📂 scripts/                        # Вспомогательные скрипты
│   └── backup_config.py               # Резервное копирование конфигурации
│
└── 📂 examples/                       # Примеры конфигураций
    └── config_example_detailed.json   # Детальный пример config.json
```

---

## 📋 Описание ключевых файлов

### Основные файлы

#### `bot.py`
**Назначение:** Точка входа в приложение
- Инициализация бота и диспетчера
- Загрузка конфигурации
- Регистрация роутеров
- Запуск polling

**Зависимости:**
- `config.py` - для доступа к настройкам
- `handlers/` - все обработчики событий

---

#### `config.py`
**Назначение:** Управление конфигурацией
- Класс `ConfigManager` для работы с JSON
- Загрузка переменных окружения из `.env`
- Методы для добавления/удаления хештегов
- Валидация конфигурации

**Экспорты:**
```python
BOT_TOKEN           # Токен бота
SOURCE_CHAT_ID      # ID исходной группы
ADMIN_IDS           # Список ID администраторов
config_manager      # Глобальный экземпляр ConfigManager
```

---

#### `config.json`
**Назначение:** Конфигурация хештегов
**Формат:**
```json
{
  "hashtags": {
    "#хештег": {
      "needs_fsm": false,
      "description": "Описание",
      "chat_id": -100123456789,
      "thread_id": 123,
      "delay": 0
    }
  }
}
```

**Редактирование:**
- Вручную (с перезапуском бота)
- Через команды бота (`/add_hashtag`, `/remove_hashtag`)

---

### Папка `handlers/`

#### `admin.py`
**Назначение:** Административные команды
**Команды:**
- `/start` - Приветствие
- `/help` - Справка
- `/add_hashtag` - Добавить хештег
- `/list_hashtags` - Список хештегов
- `/remove_hashtag` - Удалить хештег
- `/get_supergroup_id` - Получить ID группы
- `/get_thread_id` - Получить ID треда

**Особенности:**
- Проверка прав администратора
- Обработка пересланных сообщений для получения ID

---

#### `forwarding.py`
**Назначение:** Основная логика пересылки
**Функции:**
- `handle_source_chat_message()` - Обработка сообщений из исходной группы
- `forward_simple_message()` - Простая пересылка
- `handle_message_with_delay()` - Пересылка с задержкой
- `perform_delayed_forwarding()` - Выполнение отложенной пересылки

**Глобальные переменные:**
```python
pending_forwards = {}  # Словарь для хранения отложенных пересылок
```

**Workflow:**
1. Получение сообщения → Извлечение хештега
2. Проверка в whitelist
3. FSM или обычная пересылка
4. Задержка (если настроена) или мгновенная пересылка

---

#### `fsm.py`
**Назначение:** FSM обработчики для выбора типа пересылки

**States:**
```python
class ForwardingStates(StatesGroup):
    waiting_for_type_selection = State()
```

**Функции:**
- `process_type_selection()` - Обработка выбора типа (single/mediagroup)
- `perform_forwarding_single()` - Пересылка одиночного сообщения
- `perform_forwarding()` - Пересылка с задержкой и сбором дополнительных сообщений
- `create_type_selection_keyboard()` - Создание inline клавиатуры

---

### Папка `utils/`

#### `hashtag_parser.py`
**Назначение:** Утилиты для работы с хештегами

**Функции:**
```python
def extract_hashtags(text: str) -> List[str]
    """Извлечь все хештеги из текста"""

def remove_hashtag_from_text(text: str, hashtag: str) -> str
    """Удалить хештег из текста"""
```

**Особенности:**
- Поддержка русских и английских хештегов
- Поддержка цифр и подчёркиваний
- Сохранение остального текста

---

### Папка `scripts/`

#### `backup_config.py`
**Назначение:** Резервное копирование конфигурации

**Функции:**
- `backup_config()` - Создать backup с timestamp
- `restore_config()` - Восстановить из backup
- `list_backups()` - Показать все backups

**Использование:**
```bash
python scripts/backup_config.py
```

---

## 🔄 Поток данных

```
Пользователь в исходной группе
         ↓
    Отправляет: "#хештег Текст сообщения"
         ↓
    forwarding.py:handle_source_chat_message()
         ↓
    utils.hashtag_parser:extract_hashtags()
         ↓
    config_manager.get_hashtag_config()
         ↓
    ┌─────────────┐      ┌──────────────┐
    │ needs_fsm?  │  →   │ Простая      │
    │    true     │      │ пересылка    │
    └─────────────┘      └──────────────┘
         ↓                        ↓
    fsm.py:создать              forward_simple_message()
    клавиатуру выбора           или
         ↓                  handle_message_with_delay()
    Пользователь выбирает              ↓
    single/mediagroup          Целевая группа/тред
         ↓
    perform_forwarding()
         ↓
    Целевая группа/тред
```

---

## 🔐 Файлы безопасности

### `.env`
**Содержит чувствительные данные:**
```env
BOT_TOKEN=...           # Никогда не публикуйте!
SOURCE_CHAT_ID=...
ADMIN_IDS=...
```

**Защита:**
- В `.gitignore`
- Права доступа: `chmod 600 .env`
- Не коммитить в репозиторий

### `.env.example`
**Шаблон для `.env`**
- Не содержит реальных данных
- Можно публиковать в репозитории
- Инструкция для новых пользователей

---

## 📦 Зависимости (`requirements.txt`)

```
aiogram==3.4.1          # Telegram Bot API библиотека
python-dotenv==1.0.0    # Загрузка .env файлов
aiofiles==23.2.1        # Асинхронная работа с файлами
```

**Установка:**
```bash
pip install -r requirements.txt
```

---

## 🧪 Тестирование

### `test_hashtag_parser.py`
**Покрытие:**
- Извлечение хештегов
- Удаление хештегов
- Реальные сценарии использования

**Запуск:**
```bash
python test_hashtag_parser.py
```

**Результат:**
- ✅ Все тесты пройдены
- ❌ Тест провален (с описанием)

---

## 📚 Документация

| Файл | Назначение |
|------|-----------|
| `README.md` | Полное руководство с установкой и использованием |
| `QUICKSTART.md` | Быстрый старт за 5 минут |
| `USAGE_EXAMPLES.md` | Реальные примеры и сценарии |
| `FAQ.md` | Ответы на частые вопросы |
| `CHANGELOG.md` | История изменений и roadmap |
| `PROJECT_STRUCTURE.md` | Этот файл - описание структуры |

---

## 🚀 Расширение проекта

### Добавление нового обработчика

1. Создайте файл в `handlers/`:
```python
# handlers/new_handler.py
from aiogram import Router

router = Router()

@router.message(...)
async def new_handler(message):
    pass
```

2. Импортируйте в `handlers/__init__.py`:
```python
from .new_handler import router as new_router
```

3. Зарегистрируйте в `bot.py`:
```python
dp.include_router(new_router)
```

### Добавление новой утилиты

1. Создайте файл в `utils/`:
```python
# utils/new_util.py
def new_function():
    pass
```

2. Экспортируйте в `utils/__init__.py`:
```python
from .new_util import new_function
```

---

## 📊 Модульность

Проект разделён на логические модули:

- **Core** (`bot.py`, `config.py`) - Ядро системы
- **Handlers** - Бизнес-логика
- **Utils** - Вспомогательные функции
- **Scripts** - Инструменты администратора
- **Examples** - Примеры конфигураций
- **Docs** - Документация

**Преимущества:**
- ✅ Легко поддерживать
- ✅ Легко тестировать
- ✅ Легко расширять
- ✅ Понятная структура

---

## 🔍 Поиск по проекту

**Найти обработку конкретной команды:**
```bash
grep -r "/command_name" handlers/
```

**Найти использование функции:**
```bash
grep -r "function_name" .
```

**Найти TODO/FIXME:**
```bash
grep -rn "TODO\|FIXME" .
```

---

**Вопросы по структуре?** Создайте issue в репозитории!
