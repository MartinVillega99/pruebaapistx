FROM python:3.10-slim

# Instalar dependencias de sistema: Chromium y Chromium Driver
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Crear un symlink para que el binario se encuentre en /usr/bin/chromium-browser
RUN ln -s /usr/bin/chromium /usr/bin/chromium-browser

# Establecer el directorio de la app
WORKDIR /app

# Copiar requirements.txt e instalar dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del proyecto
COPY . .

# Exponer el puerto (Railway asigna el puerto a través de la variable PORT)
EXPOSE 5000

# Iniciar la app con Gunicorn
CMD ["gunicorn", "--timeout", "1200", "api_sunarp:app", "--bind=0.0.0.0:5000"]
