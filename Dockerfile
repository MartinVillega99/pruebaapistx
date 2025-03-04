FROM python:3.9-slim

# Instalar dependencias de Chrome y herramientas básicas
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    curl \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copiar y instalar dependencias de Python
COPY requirements.txt /app/
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copiar el resto de tu código
COPY . /app/

# Variables de entorno para que Selenium encuentre Chrome y ChromeDriver
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver

# Comando de inicio usando la forma "shell"
CMD gunicorn -w 4 -b 0.0.0.0:$PORT api_sunarp:app
