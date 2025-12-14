FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Optimizaciones de memoria (solo si usas TensorFlow)
# ENV TF_FORCE_GPU_ALLOW_GROWTH=true
# ENV TF_MEMORY_ALLOCATION=2048
ENV TRANSFORMERS_CACHE=/tmp/transformers_cache

ENV PORT 8080

WORKDIR /code

# Copiar solo los requerimientos primero
COPY ./requirements.txt /code/requirements.txt

# Instalar los requerimientos en una capa separada para el caché
RUN pip install --no-cache-dir -r /code/requirements.txt

# Copiar el resto del código después de instalar dependencias
COPY . /code

# CMD con la variable de entorno $PORT y timeout
CMD ["gunicorn", "--name", "marcella_api", "-w", "1", "--threads", "8", "-b", "0.0.0.0:$PORT", "--timeout", "300", "--capture-output", "--log-level", "info", "--worker-class", "uvicorn.workers.UvicornWorker", "api:app"]  # Asegúrate de que "api:app" es correcto.
