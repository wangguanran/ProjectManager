# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/
COPY pyproject.toml .
COPY README.md .

# Create necessary directories
RUN mkdir -p /app/projects /app/.cache/logs /app/.cache/cprofile

# Set volume for persistent data
VOLUME ["/app/projects", "/app/.cache"]

# Set default command
ENTRYPOINT ["python", "-m", "src"]

# Default command (can be overridden)
CMD ["--help"] 