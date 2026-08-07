# Мониторинг объявлений (mali oglasi)

Автоматическая проверка новых объявлений на https://2bike.rs/cikloberza/mali-oglasi,
фильтрация по критериям и уведомления в Telegram и на почту. Работает бесплатно
и автономно через GitHub Actions (cron), без сервера и без API сайта.

## Как это работает

1. `.github/workflows/monitor.yml` запускает `scripts/main.py` каждые 20 минут.
2. `scripts/scraper.py` скачивает страницу и парсит список объявлений.
3. Объявления сравниваются с `data/seen.json` (уже виденные) — новые проверяются
   по фильтрам из `config.yaml`.
4. При совпадении — уведомление в Telegram и на email через `scripts/notify.py`.
5. `data/seen.json` коммитится обратно в репозиторий, чтобы состояние сохранялось
   между запусками.

## Настройка

### 1. Критерии фильтрации

Редактируются в [`config.yaml`](config.yaml). Формат: список групп `any_of`.
Пост должен содержать хотя бы одно слово из **каждой** группы (группы — И,
слова внутри группы — ИЛИ). Чтобы добавить новый критерий — добавьте ещё
одну группу `any_of` в список.

### 2. Секреты репозитория

В настройках репозитория: **Settings → Secrets and variables → Actions → New repository secret**

| Секрет | Значение |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Токен бота от @BotFather |
| `TELEGRAM_CHAT_ID` | Ваш chat_id (см. ниже, как получить) |
| `GMAIL_ADDRESS` | Ваш Gmail-адрес (отправитель) |
| `GMAIL_APP_PASSWORD` | App Password Google-аккаунта (не обычный пароль) |
| `NOTIFY_EMAIL_TO` | Куда слать письма (можно тот же Gmail-адрес) |

**Telegram bot + chat_id:**
1. В Telegram: `@BotFather` → `/newbot` → получить token
2. Написать боту любое сообщение
3. Открыть `https://api.telegram.org/bot<TOKEN>/getUpdates`, найти `"chat":{"id":...}`

**Gmail App Password:**
1. Включить 2FA: https://myaccount.google.com/security
2. Создать пароль приложения: https://myaccount.google.com/apppasswords

### 3. Запуск

Workflow срабатывает автоматически по расписанию. Проверить/запустить вручную:
**Actions → Monitor mali oglasi → Run workflow**.

## Ограничения GitHub Actions (бесплатный план)

- Публичные репозитории: неограниченные минуты для cron.
- Приватные репозитории: 2000 минут/месяц бесплатно.
- Scheduled workflows автоматически отключаются, если в репозитории не было
  push более 60 дней — в этом случае нужно вручную включить workflow заново
  (Actions → workflow → Enable).
- Точность cron не гарантирована день-в-день (может быть задержка в несколько минут).

## Статус

`scripts/scraper.py` сейчас содержит заглушку — селекторы под реальную
разметку страницы объявлений ещё не заполнены.
