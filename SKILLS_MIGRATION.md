# Skills Migration Plan: OpenClaw → Ouroboros

## Приоритеты
- 🔴 **Высокий** — критично для работы Ouroboros, портировать первыми
- 🟡 **Средний** — полезно, но не блокирует
- 🟢 **Низкий** — nice to have
- ⚪ **Не нужно** — специфично для OpenClaw или неактуально

## Установленные скиллы (6)

| Скилл | Описание | Приоритет | Примечание |
|-------|----------|-----------|------------|
| critic | Стресс-тест и аудит планов, архитектур, решений | 🔴 | Саморефлексия — ядро Ouroboros |
| orchestrator | Автономный запуск задач в фоне | 🔴 | У Ouroboros уже есть task queue, можно расширить |
| tts | Текст в голос (Edge TTS → Telegram voice) | 🔴 | Голосовой интерфейс — текущий проект |
| voice | Транскрипция голосовых сообщений (Whisper) | 🔴 | Голосовой интерфейс — текущий проект |
| fast-follower | Дайджест бизнес-идей из RSS | 🟡 | Интересно для фоновой работы |
| cli-wrap | Обёртка CLI-инструментов в скиллы | 🟢 | Мета-скилл, полезен позже |

## Бэкап-список (82)

### Исследование и контент

| Скилл | Описание | Приоритет | Примечание |
|-------|----------|-----------|------------|
| agent-deep-research | Глубокий мультишаговый ресёрч | 🔴 | Ключевой для автономной работы |
| deep-research-pro | Продвинутый deep research | 🔴 | Расширенная версия |
| academic-deep-research | Академический ресёрч (arXiv, papers) | 🟡 | Для саморазвития |
| arxiv-watcher | Мониторинг новых статей на arXiv | 🟡 | Фоновый мониторинг |
| daily-ai-news-skill | Дайджест AI-новостей | 🟡 | Быть в курсе |
| news-summary | Суммаризация новостей | 🟡 | |
| competitor-research | Конкурентный анализ | 🟢 | |
| market-research | Маркетинговые исследования | 🟢 | |
| video-transcript-downloader | Скачивание транскриптов видео | 🟡 | YouTube и пр. |
| summarize | Суммаризация текстов | 🔴 | Уже bundled в OpenClaw |

### Память и самоулучшение

| Скилл | Описание | Приоритет | Примечание |
|-------|----------|-----------|------------|
| cognitive-memory | Продвинутая когнитивная память | 🔴 | Ключевой для идентичности |
| memory-manager | Управление памятью | 🔴 | |
| memory-setup | Настройка системы памяти | 🟡 | Одноразовый |
| self-reflection | Саморефлексия | 🔴 | Ядро философии Ouroboros |
| reflect-learn | Рефлексия + обучение на ошибках | 🔴 | |
| self-improving-agent | Автономное самоулучшение | 🔴 | Прямо суть Ouroboros |
| capability-evolver | Эволюция способностей | 🔴 | |
| agent-autonomy-kit | Набор для автономности агента | 🟡 | |
| context-recovery | Восстановление контекста после сбоев | 🔴 | Решает проблему провалов в памяти |
| token-optimizer | Оптимизация использования токенов | 🟡 | Экономия бюджета |
| smart-model-switching | Умное переключение моделей | 🟡 | У нас уже есть роутер |

### Веб и поиск

| Скилл | Описание | Приоритет | Примечание |
|-------|----------|-----------|------------|
| exa-web-search-free | Бесплатный веб-поиск через Exa | 🟡 | У нас уже есть Gemini Search |
| tavily-search | Поиск через Tavily API | 🟡 | Альтернатива |
| xurl | Парсинг веб-страниц (X/Twitter URL тоже) | 🔴 | Уже bundled |
| reddit-readonly | Чтение Reddit | 🟢 | |
| x-twitter | Интеграция с X/Twitter | 🟢 | |
| youtube-watcher | Мониторинг YouTube каналов | 🟡 | |

### Мониторинг и RSS

| Скилл | Описание | Приоритет | Примечание |
|-------|----------|-----------|------------|
| blogwatcher | Мониторинг блогов | 🟡 | Уже bundled |
| feed-watcher | Мониторинг RSS-фидов | 🟡 | |
| freshrss-reader | Чтение из FreshRSS | 🟢 | Нужен FreshRSS сервер |
| rss-daily-digest | Ежедневный RSS-дайджест | 🟡 | |
| openclaw-rss-feeds | RSS-фиды OpenClaw | 🟢 | Специфично для OpenClaw |
| topic-monitor | Мониторинг тем | 🟡 | |
| trend-watcher | Отслеживание трендов | 🟡 | |

### Документы и файлы

| Скилл | Описание | Приоритет | Примечание |
|-------|----------|-----------|------------|
| nano-pdf | Чтение PDF | 🔴 | Уже bundled |
| pdf-read | Чтение PDF (альтернативный) | 🟡 | |
| excel-xlsx | Работа с Excel файлами | 🟡 | |
| word-docx | Работа с Word файлами | 🟡 | |
| markdown-converter | Конвертация Markdown | 🟢 | |

### Obsidian / база знаний

| Скилл | Описание | Приоритет | Примечание |
|-------|----------|-----------|------------|
| obsidian-sync | Синхронизация с Obsidian | 🟡 | Если используешь Obsidian |
| obsidian-direct | Прямой доступ к Obsidian vault | 🟡 | |
| obsidian-daily | Ежедневные заметки Obsidian | 🟡 | |
| obsidian-tasks | Задачи из Obsidian | 🟢 | |
| obsidian-linux | Obsidian на Linux | ⚪ | Не нужно на macOS |
| save-to-obsidian | Сохранение в Obsidian | 🟡 | |
| para-second-brain | PARA-метод (второй мозг) | 🟡 | Организация знаний |

### Интеграции и коммуникация

| Скилл | Описание | Приоритет | Примечание |
|-------|----------|-----------|------------|
| telegram | Telegram интеграция | ⚪ | Уже встроено в Ouroboros |
| telegram-history | История Telegram чатов | 🟡 | Полезно для контекста |
| telegram-notify | Уведомления в Telegram | ⚪ | Уже есть |
| telegram-rich-messages | Форматированные сообщения | 🟡 | Markdown/HTML |
| gmail | Gmail интеграция | 🟢 | |
| imap-smtp-email | Email через IMAP/SMTP | 🟢 | |
| slack | Slack интеграция | 🟢 | |
| discord | Discord интеграция | 🟢 | |
| notion | Notion интеграция | 🟡 | |
| trello | Trello интеграция | 🟢 | |
| todoist | Todoist интеграция | 🟢 | |
| caldav-calendar | CalDAV календарь | 🟢 | |
| linkedin | LinkedIn интеграция | 🟢 | |

### DevOps и система

| Скилл | Описание | Приоритет | Примечание |
|-------|----------|-----------|------------|
| docker-essentials | Docker операции | 🟡 | |
| ssh-essentials | SSH операции | 🟡 | |
| tmux | Управление tmux сессиями | 🟡 | Уже bundled |
| workspace-git-backup | Бэкап workspace через git | 🟡 | |
| security-audit | Аудит безопасности | 🟢 | |
| dont-hack-me | Защита от инъекций | 🟡 | |
| moltguard | Защита системы | 🟢 | |
| fail2ban-reporter | Отчёты fail2ban | ⚪ | Нет fail2ban на маке |
| n8n-workflow-automation | n8n автоматизация | 🟢 | Нужен n8n |
| automation-workflows | Автоматизация рабочих процессов | 🟡 | |

### Голос и STT/TTS

| Скилл | Описание | Приоритет | Примечание |
|-------|----------|-----------|------------|
| openai-whisper | STT через локальный Whisper | 🔴 | Голосовой проект |
| openai-whisper-api | STT через Whisper API | 🟡 | Облачная альтернатива |

### Агенты и оркестрация

| Скилл | Описание | Приоритет | Примечание |
|-------|----------|-----------|------------|
| agent-doctor | Диагностика проблем агента | 🟡 | |
| coding-agent | Агент для написания кода | 🟡 | Уже bundled |
| openclaw-agent-optimize | Оптимизация агентов OpenClaw | ⚪ | Специфично |
| cron-doctor | Диагностика cron-задач | 🟢 | |
| cost-report | Отчёт о расходах на API | 🟡 | |
| last30days | Активность за 30 дней | 🟢 | |

### Специфичные для OpenClaw (не нужно)

| Скилл | Описание | Приоритет |
|-------|----------|-----------|
| openclaw-auto-updater | ⚪ |
| openclaw-backup | ⚪ |
| openclaw-cron-setup | ⚪ |
| openclaw-mem | ⚪ |
| claw-backup | ⚪ |
| clawdbot-backup | ⚪ |
| clawdefender | ⚪ |
| clawdex | ⚪ |
| skill-scanner | ⚪ |
| skill-vetter | ⚪ |
| auto-updater | ⚪ |
| answeroverflow | ⚪ |

### Бизнес-специфичные

| Скилл | Описание | Приоритет |
|-------|----------|-----------|
| cold-email | Холодные рассылки | 🟢 |
| copywriting | Копирайтинг | 🟢 |
| seo-optimizer-pro | SEO-оптимизация | 🟢 |
| startup-financial-modeling | Финмоделирование | 🟢 |
| startup-toolkit | Набор для стартапа | 🟢 |
| omnis-venture-intelligence | Венчурная аналитика | 🟢 |
| daily-rhythm | Дневной ритм/расписание | 🟡 |
| gemini | Gemini CLI | ⚪ |
| healthcheck | Проверка здоровья | 🟢 |
| session-logs | Логи сессий | 🟢 |
| skill-creator | Создание скиллов | 🟢 |
| weather | Погода | 🟢 |

---

## Топ-10 для первой волны портирования

1. **self-reflection** — саморефлексия (ядро)
2. **cognitive-memory** — продвинутая память
3. **context-recovery** — восстановление контекста
4. **agent-deep-research** — глубокий ресёрч
5. **critic** — стресс-тест планов
6. **tts** — текст в голос (Edge TTS)
7. **voice** — транскрипция голосовых
8. **self-improving-agent** — самоулучшение
9. **capability-evolver** — эволюция способностей
10. **reflect-learn** — обучение на ошибках
