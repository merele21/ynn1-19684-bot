"""
Тесты для модуля hashtag_parser
"""

import sys
import os

# Добавляем путь к корню проекта
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.hashtag_parser import extract_hashtags, remove_hashtag_from_text


def test_extract_hashtags():
    """Тест извлечения хештегов"""
    
    # Тест 1: Один хештег
    text1 = "#новости Важная новость"
    assert extract_hashtags(text1) == ["#новости"]
    
    # Тест 2: Несколько хештегов
    text2 = "#новости #важно Очень важная новость"
    assert extract_hashtags(text2) == ["#новости", "#важно"]
    
    # Тест 3: Хештег на русском
    text3 = "#закрытие Смена закрыта"
    assert extract_hashtags(text3) == ["#закрытие"]
    
    # Тест 4: Хештег на английском
    text4 = "#news Important update"
    assert extract_hashtags(text4) == ["#news"]
    
    # Тест 5: Смешанные языки
    text5 = "#новость_дня #breaking_news"
    assert extract_hashtags(text5) == ["#новость_дня", "#breaking_news"]
    
    # Тест 6: Нет хештегов
    text6 = "Просто текст без хештегов"
    assert extract_hashtags(text6) == []
    
    # Тест 7: Пустой текст
    assert extract_hashtags("") == []
    assert extract_hashtags(None) == []
    
    # Тест 8: Хештег с цифрами
    text8 = "#отчёт2024 Годовой отчёт"
    assert extract_hashtags(text8) == ["#отчёт2024"]
    
    print("✅ Все тесты extract_hashtags пройдены!")


def test_remove_hashtag_from_text():
    """Тест удаления хештегов"""
    
    # Тест 1: Хештег в начале
    text1 = "#новости Важная новость"
    result1 = remove_hashtag_from_text(text1, "#новости")
    assert result1 == "Важная новость"
    
    # Тест 2: Хештег в середине
    text2 = "Сегодня #важно произошло событие"
    result2 = remove_hashtag_from_text(text2, "#важно")
    assert result2 == "Сегодня произошло событие"
    
    # Тест 3: Хештег в конце
    text3 = "Событие дня #новости"
    result3 = remove_hashtag_from_text(text3, "#новости")
    assert result3 == "Событие дня"
    
    # Тест 4: Множественные пробелы после удаления
    text4 = "#отчёт    Отчёт за день"
    result4 = remove_hashtag_from_text(text4, "#отчёт")
    assert result4 == "Отчёт за день"
    
    # Тест 5: Удаление несуществующего хештега
    text5 = "#новости Важная новость"
    result5 = remove_hashtag_from_text(text5, "#другое")
    assert result5 == "#новости Важная новость"
    
    # Тест 6: Пустой текст
    assert remove_hashtag_from_text("", "#тест") == ""
    assert remove_hashtag_from_text(None, "#тест") == ""
    
    # Тест 7: Только хештег
    text7 = "#новости"
    result7 = remove_hashtag_from_text(text7, "#новости")
    assert result7 == ""
    
    # Тест 8: Несколько хештегов, удаляем один
    text8 = "#новости #важно Событие"
    result8 = remove_hashtag_from_text(text8, "#новости")
    assert result8 == "#важно Событие"
    
    print("✅ Все тесты remove_hashtag_from_text пройдены!")


def test_real_world_scenarios():
    """Тесты реальных сценариев использования"""
    
    # Сценарий 1: Сообщение с описанием
    text1 = "#закрытие Смена закрыта успешно. Все товары на месте."
    hashtags1 = extract_hashtags(text1)
    clean1 = remove_hashtag_from_text(text1, hashtags1[0])
    assert hashtags1 == ["#закрытие"]
    assert clean1 == "Смена закрыта успешно. Все товары на месте."
    
    # Сценарий 2: Медиагруппа с несколькими хештегами
    text2 = "#отчёт #день Фотоотчёт за сегодня"
    hashtags2 = extract_hashtags(text2)
    clean2 = remove_hashtag_from_text(text2, hashtags2[0])
    assert len(hashtags2) == 2
    assert "#день" in clean2  # Второй хештег остался
    
    # Сценарий 3: Хештег с эмодзи
    text3 = "#новость 🎉 Отличная новость!"
    hashtags3 = extract_hashtags(text3)
    clean3 = remove_hashtag_from_text(text3, hashtags3[0])
    assert hashtags3 == ["#новость"]
    assert clean3 == "🎉 Отличная новость!"
    
    # Сценарий 4: Длинное сообщение
    text4 = """#отчёт Подробный отчёт за день:
    1. Продажи выросли
    2. Клиенты довольны
    3. Всё отлично"""
    hashtags4 = extract_hashtags(text4)
    clean4 = remove_hashtag_from_text(text4, hashtags4[0])
    assert hashtags4 == ["#отчёт"]
    assert "Подробный отчёт за день:" in clean4
    assert "#отчёт" not in clean4
    
    print("✅ Все реальные сценарии пройдены!")


if __name__ == "__main__":
    print("🧪 Запуск тестов...\n")
    
    try:
        test_extract_hashtags()
        test_remove_hashtag_from_text()
        test_real_world_scenarios()
        
        print("\n" + "="*50)
        print("✅ ВСЕ ТЕСТЫ УСПЕШНО ПРОЙДЕНЫ!")
        print("="*50)
    except AssertionError as e:
        print(f"\n❌ Тест провален: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Ошибка при выполнении тестов: {e}")
        sys.exit(1)
