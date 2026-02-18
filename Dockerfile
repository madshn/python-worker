FROM python:3.14-slim

WORKDIR /app

# Install system deps for Pillow, CairoSVG, and fonts
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpng-dev \
    libjpeg-dev \
    libcairo2-dev \
    libgirepository1.0-dev \
    gir1.2-pango-1.0 \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

# Render sets PORT env var
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
