FROM python:3.12-slim

WORKDIR /app

# Install dependencies first for better layer caching.
# A temporary package stub satisfies setuptools during install.
COPY pyproject.toml .
RUN mkdir -p app && touch app/__init__.py \
    && pip install --no-cache-dir ".[dev]" \
    && rm -rf app

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
