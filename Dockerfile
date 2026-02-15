# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get -o Acquire::Retries=3 update && apt-get -o Acquire::Retries=3 install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy package sources and install runtime deps only (avoids dev tooling in runtime image)
COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN python -m pip install --no-cache-dir .

# Create necessary directories
RUN mkdir -p /app/projects /app/.cache/logs /app/.cache/cprofile

# Set volume for persistent data
VOLUME ["/app/projects", "/app/.cache"]

# Set default command
ENTRYPOINT ["projman"]

# Default command (can be overridden)
CMD ["--help"] 
