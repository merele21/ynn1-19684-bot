import re
from typing import List, Optional


def extract_hashtags(text: Optional[str]) -> List[str]:
    """
    Извлечь все хештеги из текста
    
    Args:
        text: Текст сообщения
    
    Returns:
        Список найденных хештегов
    """
    if not text:
        return []
    
    # Паттерн для поиска хештегов
    pattern = r'#[а-яА-ЯёЁa-zA-Z0-9_]+'
    hashtags = re.findall(pattern, text)
    
    return hashtags


def remove_hashtag_from_text(text: Optional[str], hashtag: str) -> str:
    """
    Удалить конкретный хештег из текста, сохранив остальное содержимое
    
    Args:
        text: Исходный текст
        hashtag: Хештег для удаления
    
    Returns:
        Текст без указанного хештега
    """
    if not text:
        return ""
    
    # Удаляем хештег и лишние пробелы
    result = text.replace(hashtag, "").strip()
    
    # Убираем множественные пробелы
    result = re.sub(r'\s+', ' ', result)
    
    return result
