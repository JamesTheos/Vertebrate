# Use a lightweight Python base image
FROM python:3.11-slim

WORKDIR /app

COPY Requirements.txt ./
COPY requirements-dev.txt ./

# Production deps always installed
RUN pip install --no-cache-dir -r Requirements.txt

# Dev/test deps only installed when BUILD_ENV=dev
ARG BUILD_ENV=production
RUN if [ "$BUILD_ENV" = "dev" ]; then \
        pip install --no-cache-dir -r requirements-dev.txt; \
    fi

COPY code ./code

WORKDIR /app/code

ENV PYTHONUNBUFFERED=1

EXPOSE 5001

CMD ["python", "run.py"]