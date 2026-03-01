#!/usr/bin/env python3
"""
Скрипт для резервного копирования конфигурации бота
"""

import json
import shutil
from datetime import datetime
from pathlib import Path


def backup_config():
    """Создать резервную копию config.json"""
    
    config_file = Path("config.json")
    
    if not config_file.exists():
        print("❌ Файл config.json не найден!")
        return False
    
    # Создаём директорию для бэкапов
    backup_dir = Path("backups")
    backup_dir.mkdir(exist_ok=True)
    
    # Создаём имя файла с timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = backup_dir / f"config_backup_{timestamp}.json"
    
    try:
        # Копируем файл
        shutil.copy2(config_file, backup_file)
        
        # Проверяем, что копия валидна
        with open(backup_file, 'r', encoding='utf-8') as f:
            json.load(f)
        
        print(f"✅ Резервная копия создана: {backup_file}")
        
        # Показываем статистику
        with open(config_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            hashtag_count = len(data.get("hashtags", {}))
            print(f"📊 Сохранено хештегов: {hashtag_count}")
        
        return True
    
    except Exception as e:
        print(f"❌ Ошибка при создании резервной копии: {e}")
        return False


def restore_config(backup_filename):
    """Восстановить конфигурацию из резервной копии"""
    
    backup_file = Path("backups") / backup_filename
    config_file = Path("config.json")
    
    if not backup_file.exists():
        print(f"❌ Файл {backup_file} не найден!")
        return False
    
    try:
        # Проверяем валидность backup файла
        with open(backup_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Создаём backup текущей конфигурации перед восстановлением
        if config_file.exists():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            current_backup = Path("backups") / f"config_before_restore_{timestamp}.json"
            shutil.copy2(config_file, current_backup)
            print(f"💾 Текущая конфигурация сохранена в: {current_backup}")
        
        # Восстанавливаем
        shutil.copy2(backup_file, config_file)
        
        hashtag_count = len(data.get("hashtags", {}))
        print(f"✅ Конфигурация восстановлена из: {backup_file}")
        print(f"📊 Восстановлено хештегов: {hashtag_count}")
        
        return True
    
    except Exception as e:
        print(f"❌ Ошибка при восстановлении: {e}")
        return False


def list_backups():
    """Показать список всех резервных копий"""
    
    backup_dir = Path("backups")
    
    if not backup_dir.exists():
        print("📂 Нет резервных копий")
        return
    
    backups = sorted(backup_dir.glob("config_*.json"), reverse=True)
    
    if not backups:
        print("📂 Нет резервных копий")
        return
    
    print(f"\n📋 Найдено резервных копий: {len(backups)}\n")
    
    for i, backup in enumerate(backups, 1):
        # Получаем размер файла
        size = backup.stat().st_size
        size_kb = size / 1024
        
        # Читаем количество хештегов
        try:
            with open(backup, 'r', encoding='utf-8') as f:
                data = json.load(f)
                hashtag_count = len(data.get("hashtags", {}))
        except:
            hashtag_count = "?"
        
        print(f"{i}. {backup.name}")
        print(f"   Размер: {size_kb:.2f} KB")
        print(f"   Хештегов: {hashtag_count}")
        print()


def main():
    """Главная функция"""
    
    print("🔧 Утилита резервного копирования конфигурации\n")
    print("1. Создать резервную копию")
    print("2. Восстановить из копии")
    print("3. Показать список копий")
    print("4. Выход")
    
    choice = input("\nВыберите действие (1-4): ").strip()
    
    if choice == "1":
        print("\n📦 Создание резервной копии...")
        backup_config()
    
    elif choice == "2":
        list_backups()
        backup_name = input("\nВведите имя файла для восстановления: ").strip()
        if backup_name:
            print(f"\n♻️  Восстановление из {backup_name}...")
            restore_config(backup_name)
    
    elif choice == "3":
        list_backups()
    
    elif choice == "4":
        print("👋 До свидания!")
    
    else:
        print("❌ Неверный выбор!")


if __name__ == "__main__":
    main()
