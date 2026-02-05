FROM python:3.11-slim

WORKDIR /app

# Set Python path
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port (Railway sets PORT env var)
ENV PORT=8080
EXPOSE $PORT

# Default command - run migrations then start server
CMD alembic upgrade head && uvicorn src.network.http.launch:server --host 0.0.0.0 --port $PORT
