FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    tesseract-ocr \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies with --no-cache-dir to ensure fresh installation
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user, set proper permissions, and create writable directory
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app && \
    mkdir -p /app/invoices && \
    chown -R appuser:appuser /app/invoices && \
    chmod -R 755 /app/invoices

ENV DOWNLOAD_DIR=/app/invoices

USER appuser

# Run the email processor
CMD ["python", "main.py"]