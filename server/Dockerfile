FROM python:3.13-slim AS base
COPY --from=ghcr.io/astral-sh/uv:0.10 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/opt/venv PATH="/opt/venv/bin:$PATH"
WORKDIR /app

FROM base AS deps
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

FROM deps AS test
RUN uv sync --frozen --no-install-project
COPY src ./src
COPY tests ./tests
RUN uv sync --frozen
CMD ["pytest"]

FROM deps AS runtime
COPY src ./src
RUN uv sync --frozen --no-dev
ARG GLYPHH_VERSION=dev
ENV GLYPHH_VERSION=$GLYPHH_VERSION
RUN useradd --uid 1000 --create-home glyphh
USER glyphh
EXPOSE 8080
CMD ["sh", "-c", "python -m glyphh_server.db.schema && exec uvicorn glyphh_server.main:app --host 0.0.0.0 --port 8080"]
