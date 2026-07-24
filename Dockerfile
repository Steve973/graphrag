# syntax=docker/dockerfile:1

FROM ghcr.io/astral-sh/uv:python3.12-trixie-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN --mount=type=bind,source=dist,target=/wheels,ro \
    uv pip install --system /wheels/*.whl

EXPOSE 8000

CMD ["uvicorn", "graphrag.main:app", "--host", "0.0.0.0", "--port", "8080"]
