# Usar Python 3.10 (compatible con tu versión que es Python 3.14)
FROM python:3.10-slim

# Variables de entorno para Django
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Crear directorio de trabajo
WORKDIR /app

# Instalar dependencias del sistema (gcc es necesario para algunas librerías)
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements.txt primero (mejor para caché de Docker)
COPY requirements.txt .

# Instalar las dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar TODO el código de Django
COPY . .

# Exponer el puerto 8000 (el que usa Django)
EXPOSE 8000

# Ejecutar el servidor de Django
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]