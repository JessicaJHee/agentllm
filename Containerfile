# Dockerfile for LiteLLM Proxy with Agno Custom Handler
# Works for both production and local development

FROM python:3.11-slim

# Install system dependencies including curl for healthchecks and build tools for html-to-markdown
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set working directory
WORKDIR /app

# add the application code
ADD . /app

# Install dependencies from pyproject.toml (not editable, just deps)
RUN uv sync --locked --no-dev

# Create directories for data persistence
RUN mkdir -p /app/tmp/gdrive_workspace

# Copy application source code
COPY custom_handler.py /app/
COPY proxy_config.yaml /app/
COPY src/agentllm /app/agentllm

# Set Python environment
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Expose LiteLLM proxy port
EXPOSE 8890

# Place executables in the environment at the front of the path
ENV PATH="/app/.venv/bin:$PATH"

# Reset the entrypoint, don't invoke `uv`
ENTRYPOINT []

# Run LiteLLM proxy
CMD ["litellm", "--config", "/app/proxy_config.yaml", "--port", "8890", "--host", "0.0.0.0"]
