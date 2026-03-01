"""
commands_config.py
Тексты для команд /start и /help, а также форматы вызова каждой команды.
Редактируйте этот файл, чтобы изменить справочные сообщения.
"""

# ─────────────────────────────────────────────────────────────────────────────
# /start
# ─────────────────────────────────────────────────────────────────────────────

START_TEXT = (
    "🤖 <b>Telegram Forwarder Bot</b>\n\n"

    "<b>Хештеги (SOURCE_CHAT_ID):</b>\n"
    "/add_hashtag — Добавить хештег\n"
    "/list_hashtags — Список хештегов\n"
    "/remove_hashtag — Удалить хештег\n\n"

    "<b>Keyword-правила (другие супергруппы):</b>\n"
    "/add_keyword — Добавить правило\n"
    "/list_keywords — Список правил\n"
    "/remove_keyword — Удалить правило\n\n"

    "<b>Утилиты:</b>\n"
    "/get_thread_id — Chat ID + Thread ID\n"
    "/cancel — Отменить текущую операцию\n"
    "/help — Подробная справка"
)

# ─────────────────────────────────────────────────────────────────────────────
# /help
# ─────────────────────────────────────────────────────────────────────────────

HELP_TEXT = """<b>📖 Справка по командам</b>

━━━━━━━━━━━━━━━━━━━━
<b>ХЕШТЕГИ (SOURCE_CHAT_ID)</b>
━━━━━━━━━━━━━━━━━━━━

<b>/add_hashtag</b> <code>#хештег CHAT_ID THREAD_ID [delay=N]</code>
Добавить хештег пересылки из SOURCE_CHAT_ID.
delay — задержка сбора медиагруппы (0–120 сек).

<b>/list_hashtags</b>
Показать все настроенные хештеги.

<b>/remove_hashtag</b> <code>#хештег</code>
Удалить хештег.

━━━━━━━━━━━━━━━━━━━━
<b>KEYWORD-ПРАВИЛА (другие супергруппы)</b>
━━━━━━━━━━━━━━━━━━━━

Два режима работы:

<b>1. Пересылка всего треда</b> — все сообщения из треда-источника идут в тред-цель.

<b>2. Триггер по ключевому слову</b> — пересылается только сообщение с ключевым словом \
<b>и предыдущее</b> (prev), если prev является медиа (фото/видео/аудио). \
Если prev — текст, триггер игнорируется.

<b>/add_keyword</b>
<code>source=CHAT_ID [sthread=ID] keyword=паттерн target=CHAT_ID [tthread=ID] mode=all|keyword [prev=yes/no]</code>

Параметры:
• <b>source</b> — Chat ID супергруппы-источника
• <b>sthread</b> — Thread ID треда-источника (обязателен для режимов all и keyword)
• <b>keyword</b> — триггер-паттерн; поддерживает <code>*</code> (до 5 символов), \
составные через пробел: <code>товар* дн*</code>
• <b>target</b> — Chat ID назначения
• <b>tthread</b> — Thread ID треда назначения
• <b>mode</b> — <code>all</code> (весь тред) или <code>keyword</code> (по триггеру)
• <b>prev</b> — <code>yes/no</code>, пересылать ли предыдущее сообщение (только для mode=keyword, по умолч. yes)

Примеры:
<code>/add_keyword source=-1009999999 sthread=10 keyword=итого target=-1008888888 tthread=42 mode=keyword prev=yes</code>
<code>/add_keyword source=-1009999999 sthread=10 target=-1008888888 tthread=42 mode=all</code>

<b>/list_keywords</b>
Список всех правил.

<b>/remove_keyword</b> <code>source=CHAT_ID sthread=ID keyword=паттерн</code>
Удалить правило (keyword не нужен для mode=all).

━━━━━━━━━━━━━━━━━━━━
<b>УТИЛИТЫ</b>
━━━━━━━━━━━━━━━━━━━━

<b>/get_thread_id</b>
Вызовите команду прямо в нужном топике — получите Chat ID и Thread ID.

<b>/cancel</b>
Отменить любую активную операцию (FSM).

━━━━━━━━━━━━━━━━━━━━
<b>WILDCARD в keyword</b>
━━━━━━━━━━━━━━━━━━━━

<code>*</code> совпадает с 0–5 любыми символами.
Между токенами допускается произвольный текст (до 50 символов).

Примеры:
• <code>итого</code> → найдёт «Итого», «ИТОГО»
• <code>товар* дн*</code> → найдёт «товары дня», «товаров за дня»
• <code>закрыт* смен*</code> → найдёт «закрытие смены», «закрыто всей смены»
"""

# ─────────────────────────────────────────────────────────────────────────────
# Форматы отдельных команд (используются в хендлерах для подсказок)
# ─────────────────────────────────────────────────────────────────────────────

CMD_ADD_HASHTAG_USAGE = (
    "❌ Неверный формат.\n\n"
    "Используйте:\n"
    "<code>/add_hashtag #хештег CHAT_ID THREAD_ID [delay=N]</code>\n\n"
    "Пример:\n"
    "<code>/add_hashtag #отчёт -1001234567890 123 delay=15</code>"
)

CMD_REMOVE_HASHTAG_USAGE = (
    "❌ Используйте: <code>/remove_hashtag #хештег</code>"
)

CMD_ADD_KEYWORD_USAGE = (
    "❌ Укажите параметры.\n\n"
    "Режим keyword (триггер + prev media):\n"
    '<code>/add_keyword source=-100XXX sthread=ID keyword="слово1 слов*2" '
    "target=-100YYY tthread=ID mode=keyword [prev=yes]</code>\n\n"
    "Режим all (весь тред):\n"
    "<code>/add_keyword source=-100XXX sthread=ID "
    "target=-100YYY tthread=ID mode=all</code>\n\n"
    "💡 Составной keyword — обязательно в кавычках: keyword=\"товар* дня\""
)

CMD_REMOVE_KEYWORD_USAGE = (
    "❌ Используйте:\n"
    "<code>/remove_keyword source=CHAT_ID sthread=THREAD_ID [keyword=\"паттерн\"]</code>\n\n"
    "Для mode=all keyword не нужен."
)