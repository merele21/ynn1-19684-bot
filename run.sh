#!/bin/bash

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}🤖 Telegram Forwarder Bot - Запуск${NC}"
echo ""

# Проверка наличия .env файла
if [ ! -f .env ]; then
    echo -e "${RED}❌ Файл .env не найден!${NC}"
    echo -e "${YELLOW}Создайте .env файл на основе .env.example${NC}"
    echo ""
    echo "Выполните команду:"
    echo "  cp .env.example .env"
    echo ""
    echo "Затем отредактируйте .env и укажите:"
    echo "  - BOT_TOKEN (получите у @BotFather)"
    echo "  - SOURCE_CHAT_ID (ID исходной группы)"
    echo "  - ADMIN_IDS (ваш Telegram ID)"
    exit 1
fi

# Проверка установки зависимостей
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}⚙️  Виртуальное окружение не найдено. Создаю...${NC}"
    python3 -m venv venv
    echo -e "${GREEN}✅ Виртуальное окружение создано${NC}"
fi

# Активация виртуального окружения
echo -e "${YELLOW}📦 Активация виртуального окружения...${NC}"
source venv/bin/activate

# Установка/обновление зависимостей
echo -e "${YELLOW}📥 Проверка зависимостей...${NC}"
pip install -r requirements.txt -q

echo ""
echo -e "${GREEN}✅ Всё готово!${NC}"
echo -e "${GREEN}🚀 Запуск бота...${NC}"
echo ""

# Запуск бота
python bot.py
