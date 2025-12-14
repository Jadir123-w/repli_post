FROM python:3.13-slim

# Fix typo in environment variable (PYTHONBUFFERED -> PYTHONUNBUFFERED)
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Add memory optimization environment variables
ENV TF_FORCE_GPU_ALLOW_GROWTH=true
ENV TF_MEMORY_ALLOCATION=2048
ENV TRANSFORMERS_CACHE=/tmp/transformers_cache

WORKDIR /code

RUN apt-get update && apt-get install -y ffmpeg
RUN apt-get update && apt-get install -y libmagic-dev

# Instalar Typst
ENV TYPST_VERSION=v0.11.0
RUN apt-get update && apt-get install -y --no-install-recommends wget ca-certificates xz-utils && \
    wget https://github.com/typst/typst/releases/download/${TYPST_VERSION}/typst-x86_64-unknown-linux-musl.tar.xz && \
    tar -xf typst-x86_64-unknown-linux-musl.tar.xz && \
    mv typst-x86_64-unknown-linux-musl/typst /usr/local/bin/ && \
    rm -rf typst-x86_64-unknown-linux-musl && \
    rm typst-x86_64-unknown-linux-musl.tar.xz && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Primero copiamos solo el requirements.txt para aprovechar la caché de Docker
COPY app/requirements.txt /code/requirements.txt

# Instalar dependencias usando la ruta absoluta
RUN pip install --no-cache-dir -r /code/requirements.txt

# Primero copiamos el archivo de credenciales para asegurar su disponibilidad
COPY app/config/conauti-core-8c0a52a81bdb.json /code/app/config/conauti-core-8c0a52a81bdb.json

# Luego copiamos el resto de la aplicación
COPY app /code/app

# Verificar que el archivo de credenciales existe y tiene los permisos correctos
RUN ls -la /code/app/config/conauti-core-8c0a52a81bdb.json && \
    chmod 600 /code/app/config/conauti-core-8c0a52a81bdb.json

ENV PORT=8080

ENV PYTHONPATH=/code

# Modify gunicorn command for better memory management
# Reduce workers to 1, add threads, and use a standard WSGI worker for Flask compatibility
CMD ["gunicorn", "-w", "1", "--threads", "8", "-b", "0.0.0.0:8080", "--timeout", "0", "--capture-output", "--log-level", "info", "app.api:app"]
