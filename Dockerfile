FROM python:3.12-slim

WORKDIR /app

# Устанавливаем системные зависимости, если нужны (например, для сборки)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем Poetry
RUN pip install --no-cache-dir poetry

# Отключаем создание виртуальных окружений внутри контейнера (ставим зависимости глобально в систему контейнера)
RUN poetry config virtualenvs.create false

# Сначала копируем только файлы зависимостей для кэширования слоев Docker
COPY pyproject.toml poetry.lock ./

# Устанавливаем зависимости (без самого проекта)
RUN poetry install --no-root --no-interaction --no-ansi

# Копируем остальной код проекта
COPY . .

RUN chmod +x start.sh

# Запускаем через CMD
CMD ["./start.sh"]