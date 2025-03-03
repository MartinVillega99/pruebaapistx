FROM python:3.10-slim

# Instalar dependencias de sistema
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
# Instalar Google Chrome
    && wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update && apt-get install -y google-chrome-stable \
# Instalar ChromeDriver
    && CHROMEDRIVER_VERSION=$(curl -sS https://chromedriver.storage.googleapis.com/LATEST_RELEASE) \
    && wget -O /tmp/chromedriver.zip https://chromedriver.storage.googleapis.com/$CHROMEDRIVER_VERSION/chromedriver_linux64.zip \
    && unzip /tmp/chromedriver.zip -d /usr/local/bin/ \
    && rm /tmp/chromedriver.zip \
    && chmod +x /usr/local/bin/chromedriver \
# Limpiar cache
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Crear carpeta de la app
WORKDIR /app

# Copiar requirements e instalarlos
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto de tu proyecto
COPY . .

# Exponer el puerto (Render asigna uno dinámico, pero pones 5000 por convención)
EXPOSE 5000

# Iniciar con Gunicorn
CMD ["gunicorn", "api_sunarp:app", "--bind=0.0.0.0:5000"]
