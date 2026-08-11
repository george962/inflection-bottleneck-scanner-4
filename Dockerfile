FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m pip install --upgrade pip && pip install ".[dashboard,llm]"

COPY config ./config
COPY dashboard ./dashboard
COPY scripts ./scripts
COPY published ./published
RUN mkdir -p /app/data /app/outputs /app/published

CMD ["inflection-scanner", "research", "--deep", "180", "--research-count", "20", "--top", "30"]
