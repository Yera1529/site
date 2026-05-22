# Авто-деплой: настройка

Автоматический деплой при `git push` в `master` через GitHub Actions + SSH.

---

## 1. GitHub Secrets

Перейди в **Settings → Secrets and variables → Actions → New repository secret** и добавь:

| Secret | Описание | Пример |
|--------|----------|--------|
| `SSH_HOST` | IP или домен сервера | `185.100.50.25` |
| `SSH_USER` | Пользователь SSH | `root` или `deploy` |
| `SSH_PORT` | Порт SSH | `22` |
| `SSH_PRIVATE_KEY` | Приватный ключ (весь, включая `-----BEGIN...-----END...`) | см. шаг 2 |
| `PROJECT_PATH` | Абсолютный путь к проекту на сервере | `/root/site` или `/home/deploy/PredstavlenieAi` |

---

## 2. Подготовка сервера (один раз)

### 2.1. Сгенерировать деплой-ключ

На сервере (или на любой машине):

```bash
ssh-keygen -t ed25519 -C "gh-deploy" -f ~/.ssh/gh_deploy -N ""
```

### 2.2. Добавить публичный ключ на сервер

```bash
cat ~/.ssh/gh_deploy.pub >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

### 2.3. Приватный ключ → GitHub Secret

```bash
cat ~/.ssh/gh_deploy
```

Скопируй **всё** содержимое (включая `-----BEGIN OPENSSH PRIVATE KEY-----` и `-----END OPENSSH PRIVATE KEY-----`) и вставь в GitHub Secret `SSH_PRIVATE_KEY`.

### 2.4. Убедиться, что репозиторий склонирован

```bash
cd /путь/к/проекту
git remote -v
# origin  https://github.com/Yera1529/site.git (fetch)
git branch
# * master
```

### 2.5. Проверить секреты на сервере

Эти файлы **НЕ приходят из git** (в `.gitignore`). Они должны лежать вручную:

```bash
ls -la backend/credentials.json   # Vertex AI сервис-аккаунт (>0 байт)
ls -la backend/.env                # переменные окружения
ls -la .env                        # docker compose переменные (если есть)
```

> ⚠️ `git reset --hard origin/master` НЕ трогает untracked-файлы. Секреты сохранятся.  
> ❌ НЕ делай `git clean -fdx` — это удалит все untracked-файлы, включая секреты!

### 2.6. Docker и права

```bash
docker --version           # Docker установлен
docker compose version     # Docker Compose v2 (или docker-compose --version для v1)
groups                     # пользователь в группе 'docker'
```

Если нет в группе `docker`:
```bash
sudo usermod -aG docker $USER
# перелогиниться
```

---

## 3. Как это работает

1. Ты пушишь в `master` → GitHub Actions запускает workflow `.github/workflows/deploy.yml`.
2. Workflow подключается по SSH к серверу.
3. На сервере выполняется:
   - `git fetch --all` + `git reset --hard origin/master` — обновляет код
   - `docker compose up -d --build` — пересобирает и перезапускает контейнеры
   - `docker image prune -f` — чистит старые образы
   - `curl http://localhost:8000/api/health` — health-check (падает, если бэкенд не ответил)

---

## 4. Проверка

После добавления всех секретов — сделай тестовый push:

```bash
git commit --allow-empty -m "test: trigger deploy"
git push origin master
```

Зайди в **Actions** → увидишь запуск → статус Deploy OK / Failed.

Или запусти вручную: **Actions → Deploy to server → Run workflow**.

---

## 5. Важно: модель на проде

> ⚠️ **В UI продакшена модель отображается как Qwen3-30B, а `AIService` написан под Google Vertex Gemini.**

Авто-деплой доставляет код, но **не меняет модель**. Если на сервере реально работает Qwen/Ollama — Vertex-реранк будет падать, и подбор норм останется мусорным (одинаковые 76%, нерелевантные кодексы).

**Варианты:**
1. На сервере используется Vertex Gemini → убедись, что `credentials.json` и `.env` настроены как при локальном тесте.
2. На сервере используется Qwen/Ollama → нужно адаптировать `AIService.rerank_laws()` под эту модель (отдельная задача).
