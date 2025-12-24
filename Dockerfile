# ============================================================
# AXI V12 - Agent Souverain avec Internet
# Dockerfile avec dépendances système pour lxml/trafilatura
# ============================================================

FROM python:3.11-slim

# Variables pour voir les logs immédiatement
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Dépendances système pour lxml/trafilatura
RUN apt-get update && apt-get install -y \
    gcc \
    libxml2-dev \
    libxslt-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Installation Python (une seule fois au build)
RUN pip install --no-cache-dir \
    anthropic \
    psycopg2-binary \
    apscheduler \
    pytz \
    openpyxl \
    duckduckgo-search \
    trafilatura

# COPIER LES FICHIERS SOURCE
COPY . .

# Port exposé
EXPOSE 8080

# Démarrage
CMD ["python", "main.py"]
