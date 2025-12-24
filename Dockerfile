# AXI V10.2 - Stable
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install --no-cache-dir \
    anthropic \
    psycopg2-binary \
    apscheduler \
    pytz \
    openpyxl

COPY . .

EXPOSE 8080

CMD ["python", "main.py"]
