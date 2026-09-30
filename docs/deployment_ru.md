# Запуск и эксплуатация Smart Chef

Подробный технический гайд для команды. Для знакомства с продуктом и демонстрации проекта откройте [README](../README.md).

## Быстрый старт

Все команды ниже выполняются из **корня репозитория** в Bash (Linux, macOS или WSL). Используется корневой `backend/`: вложенный `recipe-ai-backend/` — другая, более ранняя версия, без журналов.

Для Docker нужны Git, Docker Engine/Desktop и Compose с поддержкой `docker compose up --wait`. Python 3 на хосте нужен только для smoke-проверки. Для запуска без Docker нужны Python ≥ 3.12, `uv` и Node.js/npm для сервера фронтенда. Нужны ключ OpenAI, доступная этому ключу модель и интернет: сервер обращается к OpenAI/Supabase, браузер загружает CDN и модель MediaPipe.

Установка Docker: [Engine на Ubuntu](https://docs.docker.com/engine/install/ubuntu/) и [Compose](https://docs.docker.com/compose/install/).

```bash
git clone https://github.com/alikhan-kai/smart-chef-motion.git
cd smart-chef-motion
docker version
docker compose version
```

Если используете форк, замените адрес репозитория своим. Если проект уже скачан, достаточно перейти в его корень.

### Вариант A: Docker

```bash
test -f .env || cp .env.example .env
```

Откройте `.env`, укажите реальный `OPENAI_API_KEY` и выбранный `OPENAI_MODEL`. Для постоянного хранения сначала выполните [настройку Supabase](#настройка-supabase). Затем:

```bash
docker compose config --quiet
docker compose up --build -d --wait
docker compose ps
python3 scripts/smoke_docker.py
```

- Интерфейс: http://localhost:8080
- Документация API: http://localhost:8000/docs
- API через фронтенд: http://localhost:8080/api/openapi.json

Порты `8000` и `8080` должны быть свободны. Они привязаны к `127.0.0.1`, поэтому напрямую с другого компьютера недоступны. Фронтенд в контейнере использует `/api`; Nginx направляет эти запросы в `backend:8000`, удаляя префикс `/api`. Конфигурация находится в [compose.yaml](../compose.yaml) и [deploy/nginx.conf](../deploy/nginx.conf).

Для проверки запуска без реального ключа можно выполнить `BACKEND_ENV_FILE=./.env.example docker compose up --build -d --wait`. Генерация с ключом-заглушкой работать не будет. При последующих командах используйте тот же `BACKEND_ENV_FILE` либо настройте корневой `.env` и заново выполните `up`.

### Вариант B: локально

В первом терминале установите зависимости из `uv.lock` и запустите API:

```bash
test -f .env || cp .env.example .env
# Заполните .env перед запуском API.
uv sync --frozen --extra dev --python 3.12
uv run --frozen uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

В новом терминале:

```bash
npx serve --listen tcp://127.0.0.1:8080
```

Откройте http://localhost:8080 и разрешите доступ к камере. Камера работает на `localhost` и на HTTPS.

Без Docker [js/api-config.js](../js/api-config.js) обращается к `http://localhost:8000`. CORS разрешает `http://localhost:8080` и `http://127.0.0.1:8080`; другой origin потребует изменения конфигурации. Сервер `serve` здесь предназначен только для локальной разработки: он раздаёт каталог репозитория. Для публичного размещения используйте Docker-фронтенд с отдельным набором статических файлов. `--reload` перезапускает процесс при изменениях и очищает чаты в памяти.

## Конфигурация

Переменные читаются из `.env` (шаблон: [.env.example](../.env.example)).

| Переменная | Обязательна | По умолчанию | Описание |
|---|---|---|---|
| `OPENAI_API_KEY` | да | — | Ключ OpenAI |
| `OPENAI_MODEL` | да | `gpt-6-luna` в `.env.example` | Модель для генерации рецептов |
| `OPENAI_TIMEOUT_SECONDS` | нет | `60` | Таймаут запроса к модели |
| `TWO_STEP_MODE` | нет | `false` | Запасной режим: поиск и текст, затем конвертация в строгий JSON |
| `OPENAI_PRICING_MODEL` и тарифы | нет | GPT-6 Luna Standard short-context | Оценка стоимости в JSON-логах ([инструкция](../docs/api_cost_logging.md)) |
| `SUPABASE_URL` | нет | пусто | Адрес проекта Supabase для хранения на бэкенде |
| `SUPABASE_SERVICE_KEY` | нет | пусто | Service role key (не anon), только для бэкенда |
| `YANDEX_ALICE_SKILL_ID` | нет | пусто | ID навыка для проверки входящих webhook-запросов Алисы |

Если `SUPABASE_*` не заданы, книга рецептов и журналы хранятся в памяти процесса и пропадают при перезапуске. Чтобы включить постоянное хранение, выполните SQL-миграцию из [docs/recipe_magazine_contract.md](../docs/recipe_magazine_contract.md) в SQL-редакторе Supabase.

Для включения хранения нужны **обе** переменные: при отсутствии любой из них бэкенд использует память. Compose также читает `BACKEND_ENV_FILE` (по умолчанию `./.env`) и `IMAGE_TAG` (по умолчанию `local`). Это настройки развёртывания, а не LLM.

После изменения `.env` выполните `docker compose up -d --force-recreate backend`: обычный `restart` не подхватывает новое окружение контейнера. После изменения кода или `js/config.js` нужна пересборка образов. Не публикуйте `.env`, ключ OpenAI и service role key в Git, браузерных файлах или логах.

Есть и необязательные настройки чата (`REVISE_MODEL`, `REVISE_USE_WEB_SEARCH`, `REVISE_HISTORY_MESSAGES`, `REVISE_FALLBACK_TO_FULL_REGENERATION`), см. [llm/config.py](../llm/config.py).

### Настройка Supabase

В приложении два отдельных подключения:

| Подключение | Где настроить | Для чего |
|---|---|---|
| Бэкенд | `SUPABASE_URL` и `SUPABASE_SERVICE_KEY` в корневом `.env` | Таблицы `recipe_book_entries`, `recipe_magazines`, `recipe_magazine_items`, `recipe_magazine_views` |
| Браузер | `SUPABASE_URL` и публичный `SUPABASE_ANON_KEY` в [js/config.js](../js/config.js) | Вход, XP, история в таблицах `users` и `ai_requests` |

1. Для нового проекта Supabase выполните SQL из [контракта журналов](../docs/recipe_magazine_contract.md#persistence), включая функцию `increment_magazine_view_count`. Для существующей БД сначала сравните схему: повторный `CREATE TABLE` не обновляет таблицы. Для сохранения с витрины требуется колонка `recipe_magazine_items.source_magazine_title`.
2. Заполните обе переменные бэкенда. Service role key используется только сервером.
3. Для своего проекта обновите URL и **публичный** ключ в `js/config.js`. Укажите один и тот же проект в браузере и на сервере, если не планируете специально разделять данные.
4. Подготовьте также `users`, `ai_requests` и права доступа для браузера. SQL из контракта журналов их не создаёт; полной миграции этих старых таблиц в репозитории нет. Для нового окружения потребуется схема и политики из используемого командой проекта Supabase.
5. Пересоберите стек и проверьте вход, подтверждение рецепта, создание и публикацию журнала.

Пустые `SUPABASE_*` в `.env` отключают только постоянное хранение на бэкенде: браузер продолжает обращаться к проекту из `js/config.js`.

### Что сохраняется после перезапуска

| Данные | Хранилище | После перезапуска бэкенда |
|---|---|---|
| Чаты и версии рецептов | Память процесса | Теряются всегда |
| Привязки и команды Алисы | Память процесса | Требуется повторная привязка |
| Книга рецептов и журналы | Supabase при заполненных настройках, иначе память | Сохраняются только в Supabase |
| История браузера, аккаунты и XP | Supabase через фронтенд | Не удаляются перезапуском контейнеров |

Оставляйте **один экземпляр бэкенда и один worker**, как в Dockerfile: несколько процессов не разделяют чаты. В Compose нет контейнера PostgreSQL и тома с резервной копией БД. Резервное копирование Supabase настраивается отдельно; откат образов не восстанавливает данные.

## Деплой на сервер и HTTPS

Ниже — схема для Linux/VPS или EC2 с Docker и `cloudflared` на хосте. Подробнее: [DEPLOYMENT.md](../DEPLOYMENT.md).

1. Установите Docker Engine и Compose, Git и Python 3 для проверок. Включите Docker при загрузке: `sudo systemctl enable --now docker`. Проверьте доступ текущего пользователя к `docker ps`.
2. Клонируйте репозиторий на сервер, настройте корневой `.env` и Supabase по инструкции выше. Для файла с секретами задайте `chmod 600 .env`.
3. Соберите релиз с тегом коммита и проверьте его локально на сервере:

   ```bash
   export IMAGE_TAG=$(git rev-parse --short HEAD)
   docker compose config --quiet
   docker compose up --build -d --wait
   python3 scripts/smoke_docker.py
   ```

4. Создайте Cloudflare Tunnel для своего домена. Установите `cloudflared` на сервер и выполните команду установки системного сервиса из панели Cloudflare, используя токен этого туннеля. Токен не помещайте в репозиторий. См. [официальную инструкцию Cloudflare](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/get-started/create-remote-tunnel-api/).
5. Укажите публичный hostname, например `chef.example.com`, и сервис **`http://localhost:8080`**. Весь сайт, включая `/api/*`, должен идти на фронтенд Nginx. Если `cloudflared` запускается контейнером, подключите его к сети Compose и используйте `http://frontend:80`: `localhost` внутри контейнера обозначает сам контейнер.
6. Проверьте туннель и сайт:

   ```bash
   sudo systemctl status cloudflared --no-pager
   sudo journalctl -u cloudflared -n 100 --no-pager
   python3 scripts/smoke_docker.py --frontend-url https://chef.example.com
   ```

Для этой схемы не нужно открывать входящие `8000` и `8080` в firewall/Security Group. Доступ администратора настройте отдельно. Серверу нужен исходящий доступ к DNS, реестрам образов, OpenAI, Supabase и Cloudflare Tunnel. HTTPS обеспечивает публичная точка входа; контейнер Nginx слушает HTTP внутри сервера.

Не включайте принудительное кеширование `/api/*` в Cloudflare. Статика сейчас отдаётся с `Cache-Control: no-store`, чтобы новая версия появлялась после обновления страницы. Nginx ограничивает тело запроса размером `10m` и ждёт ответ бэкенда до 120 секунд. Настройка приватного навыка Алисы и webhook описана отдельно в [docs/yandex_alice_integration.md](../docs/yandex_alice_integration.md).

Текущий вход — хакатонный прототип: сервер доверяет `X-User-Id`, а браузер использует `fakeHash` и собственную таблицу пользователей. Для полноценного публичного сервиса ещё нужны проверяемая сервером аутентификация, корректные политики доступа к БД и ограничения запросов. HTTPS сам по себе это не реализует.

## Обновление, откат и обслуживание

Запишите тег текущего рабочего релиза перед обновлением. Из чистой рабочей копии на выбранной ветке:

```bash
git pull --ff-only
export IMAGE_TAG=$(git rev-parse --short HEAD)
docker compose build
docker compose up -d --no-build --pull never --wait
python3 scripts/smoke_docker.py
```

Сборка выполняется при работающих старых контейнерах; при замене возможен короткий простой. Исходники копируются в образы, поэтому `git pull` или `docker compose restart` без сборки не обновляют приложение. Изменения схемы БД применяются отдельно: автоматического запуска миграций нет.

Для отката к сохранённой паре образов замените `previous-commit` реальным предыдущим тегом:

```bash
export IMAGE_TAG=previous-commit
docker compose up -d --no-build --pull never --wait
python3 scripts/smoke_docker.py
```

Откат применим при совместимых Compose, окружении и схеме БД. Он не возвращает старый `.env` или данные Supabase. Сохраните предыдущие образы до проверки релиза. В новых терминалах снова задавайте нужный `IMAGE_TAG`, иначе Compose выберет `local`.

| Задача | Команда |
|---|---|
| Состояние контейнеров | `docker compose ps` |
| Последние ошибки API | `docker compose logs --tail=150 backend` |
| Следить за логами | `docker compose logs -f --tail=100 backend frontend` |
| Перезапустить API | `docker compose restart backend` |
| Остановить стек | `docker compose down` |
| Использование ресурсов | `docker stats --no-stream` |
| Место, занятое Docker | `docker system df` |

Перезапуск и остановка очищают состояние в памяти. Политика `restart: unless-stopped` перезапускает завершившийся контейнер, но не исправляет недоступную БД; контейнеры после `down` нужно снова запустить через `up`. Следите за диском и настройте ротацию Docker-логов на сервере: в текущем Compose отдельной настройки ротации нет. Логи затрат API описаны в [docs/api_cost_logging.md](../docs/api_cost_logging.md).

## Проверка деплоя и диагностика

`python3 scripts/smoke_docker.py` проверяет статику, маршруты API, чтение списков и CORS, а также отсутствие доступа к файлам репозитория через Docker-фронтенд. Он не записывает данные и не вызывает модель. Статус `healthy` проверяет только доступность приложения — не ключ OpenAI, запись в Supabase или камеру.

После выкладки вручную проверьте: вход → генерация → уточнение → подтверждение рецепта → создание журнала → публикация → просмотр другим тестовым пользователем → приготовление с камерой. Генерация расходует API-бюджет. Сохранность данных после перезапуска проверяйте на тестовом окружении, учитывая потерю чатов.

| Симптом | Что проверить |
|---|---|
| `docker compose` не найден или нет `--wait` | Установку/версию Compose plugin |
| Ошибка доступа к Docker socket | Запущен ли Docker и есть ли у пользователя права на daemon |
| Порт занят | `docker ps`, слушающие процессы на `8000`/`8080`; параметры `ports` в Compose |
| `502` через Nginx | `docker compose ps`, логи `backend` и `frontend`; доступность `backend:8000` |
| Журналы возвращают `404` | Есть ли `/recipe-magazines` в `/api/openapi.json`; собран ли корневой бэкенд |
| Генерация возвращает `4xx/5xx` | Ответ запроса в Network и логи API: ключ, доступ к модели, лимиты, таймаут |
| «Не удалось сохранить/опубликовать журнал» | В DevTools → Network найдите неуспешный `POST /api/recipe-magazines`, `PUT .../items`, `PUT .../cover` или `POST .../share`; сохраните статус и Response и сопоставьте с логами **сервера этого сайта** |
| Supabase сообщает об отсутствующей таблице/колонке | Схему из контракта журналов, включая `source_magazine_title`; правильность проекта в настройках |
| `Temporary failure in name resolution` | DNS и исходящую сеть именно контейнера, адрес Supabase; это сетевая ошибка, её нельзя подтвердить одним сообщением интерфейса |
| Обложка не загружается, `413` | Лимит Nginx `10m`, учитывая весь multipart-запрос |
| Рецепты видны, но журналы не работают | Браузер читает `ai_requests` отдельно от бэкенда; успешное чтение истории не подтверждает настройку серверного Supabase |
| После перезапуска всё исчезло | Обе ли настройки Supabase заполнены; чаты всегда остаются в памяти |
| Камера недоступна | HTTPS/localhost, разрешение браузера и доступ к CDN/модели MediaPipe |
| После выкладки старый интерфейс | Пересборку frontend, обновление страницы и правила кеширования Cloudflare |

Текущий интерфейс журналов скрывает детали части ошибок и не проверяет HTTP-статус некоторых запросов. Поэтому сообщение интерфейса или закрывшееся окно само по себе не подтверждает успешную запись. При диагностике ориентируйтесь на ответы Network и серверные логи; не отправляйте ключи и содержимое `.env`.
