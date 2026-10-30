FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=7860

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN python manage.py collectstatic --noinput

# Hugging Face runs with a non-root user with UID 1000
RUN useradd -m -u 1000 user && chown -R user:user /app
USER user

EXPOSE 7860

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:7860", "--workers", "2", "--timeout", "60"]
