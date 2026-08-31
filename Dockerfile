FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot ./bot
COPY prompts ./prompts
COPY schema.sql ./

# Root emas — xavfsizroq
RUN useradd --create-home --uid 1000 matustoz && chown -R matustoz:matustoz /app
USER matustoz

CMD ["python", "-m", "bot.main"]
