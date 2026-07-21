# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.

# =============================================================================
# Stage 1: Build stage
# =============================================================================
FROM python:3.14-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libcairo2-dev \
    libffi-dev \
    libgdk-pixbuf-2.0-dev \
    libpango1.0-dev \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python3 -m venv /opt/venv

# Set working directory for build
WORKDIR /build

# Install Python dependencies
COPY requirements.txt .
RUN /opt/venv/bin/pip install --no-cache-dir --upgrade pip && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# =============================================================================
# Stage 2: Runtime stage
# =============================================================================
FROM python:3.14-slim AS runtime

# Install only runtime dependencies required by weasyprint and other libraries
# Also install tini as a minimal init system for proper signal handling
# Install PostgreSQL and MySQL clients for database backups
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-dejavu-core \
    libcairo2 \
    libffi8 \
    libgdk-pixbuf-2.0-0 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    tini \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash coati

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv

# Set working directory
WORKDIR /app

# Copy application code
COPY . .

# Instalar paquete usando el pip del venv
RUN /opt/venv/bin/pip install --no-cache-dir -e . \
    && chmod +x docker-entrypoint.sh \
    && chown -R coati:coati /app

# Switch to non-root user
USER coati

# Expose port
EXPOSE 5000

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_APP=app:app \
    FLASK_ENV=production

# Use tini as init system for proper signal handling
ENTRYPOINT ["/usr/bin/tini", "--", "/app/docker-entrypoint.sh"]

# Run the application
CMD ["/opt/venv/bin/python", "app.py"]
