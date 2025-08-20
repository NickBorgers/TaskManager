# Base stage for shared dependencies
FROM python:3.11-slim as base

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create a non-root user
RUN useradd --create-home --shell /bin/bash app && \
    chown -R app:app /app
USER app

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Create logs directory
RUN mkdir -p /app/logs

# Create a directory for persistent state
RUN mkdir -p /app/state

# Test stage
FROM base as test

# Switch back to root to install test dependencies
USER root

# Copy test requirements
COPY test_requirements.txt .

# Install test dependencies
RUN pip install --no-cache-dir -r test_requirements.txt

# Create test directories
RUN mkdir -p /app/tests /app/htmlcov

# Switch back to app user
USER app

# Set test environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV NOTION_INTEGRATION_SECRET=test-token

# Test command
CMD ["pytest", "tests/", "-v", "--cov=scripts", "--cov-report=term-missing", "--cov-report=html:htmlcov"]

# Production stage
FROM base as production

# Default command - run the scheduler
CMD ["python", "scripts/scheduler.py"] 