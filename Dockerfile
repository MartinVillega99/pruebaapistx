FROM python:3.10-slim

# Instalar dependencias de sistema: Chromium y su driver
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Crear un symlink para que el binario se encuentre en /usr/bin/chromium-browser
RUN ln -s /usr/bin/chromium /usr/bin/chromium-browser

# Crear carpeta de la app
WORKDIR /app

# Copiar requirements e instalarlos
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto de tu proyecto
COPY . .

# Exponer el puerto
EXPOSE 5000

# Iniciar la app con Gunicorn
CMD ["gunicorn", "--timeout", "1200", "api_sunarp:app", "--bind=0.0.0.0:5000"]
