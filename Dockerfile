FROM python:3.13-slim

# Prevent .pyc files and force stdout/stderr flushing
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Default port (Railway overrides $PORT at runtime)
ENV PORT=8000

WORKDIR /app

# Install dependencies first for clean layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app ./app

# Create and switch to a non-root user for container security
RUN adduser --disabled-password --gecos "" appuser
USER appuser

# Railway injects $PORT dynamically; fall back to 8000 locally
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
