FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN python -m pip install --upgrade pip && \
    pip install ".[dashboard]"

COPY config ./config
COPY dashboard ./dashboard
COPY scripts ./scripts
RUN mkdir -p /app/data /app/outputs

CMD ["inflection-scanner", "scan", "--top", "20"]
