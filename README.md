# course-services

Это мой учебный проект по Python backend. Тут задумано четыре сервиса: `course-service`, `bff`, `code-coordinator` и `plagiarism-service`. Пока работает только `course-service`, а в остальных папках лежат заглушки.

## Как запустить

Нужны Python 3.14 и `uv`. Перейти в папку сервиса и установить зависимости:

```bash
cd course-service
uv sync
```

В этой же папке создать файл `.env`:

```dotenv
APP__TITLE="Course Service"
APP__DESCRIPTION="Course service API"
APP__SUMMARY="Course service"
APP__VERSION="0.1.0"
```

Запустить приложение:

```bash
uv run uvicorn src.main:app --host 127.0.0.1 --port 8888 --env-file .env --log-config log-config.yaml
```

После запуска можно открыть `http://127.0.0.1:8888/service` или `http://127.0.0.1:8888/docs`.

## Тесты

Из папки `course-service`:

```bash
uv run pytest
```

## Что я понял

Я разобрался, как настроить своё приложение и запустить его через `uv`. Ещё понял, как связаны основные части: настройки читаются из `.env`, `main.py` создаёт приложение, роутер принимает запрос, а функция сервиса готовит ответ. Тесты помогают проверить, что всё это работает вместе.
