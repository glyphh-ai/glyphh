FROM python:3.13-slim AS base
COPY --from=ghcr.io/astral-sh/uv:0.10 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/opt/venv UV_NO_CACHE=1 PATH="/opt/venv/bin:$PATH"
WORKDIR /app

# Ada Cloud's kernel is ada-private at the commit uv.lock pins, read over SSH with a read-only deploy key given as the
# build secret ada_deploy_key (CI: the ADA_DEPLOY_KEY secret; Fly: flyctl deploy --build-secret). The key is never in
# a layer, and the image is pushed only to private registries (Fly's, and ghcr.io/glyphh-ai/server, private).
FROM base AS deps
RUN apt-get update && apt-get install -y --no-install-recommends git openssh-client && rm -rf /var/lib/apt/lists/*
RUN git config --global url."ssh://git@github.com/glyphh-ai/ada-private".insteadOf "https://github.com/glyphh-ai/ada-private"
# ssh refuses a key file without its final newline ("error in libcrypto"), and flyctl's --build-secret NAME=VALUE drops
# it: this wrapper copies the key to a private temporary file with the newline put back, for each ssh call only.
RUN printf '%s\n' '#!/bin/sh' \
      'key=$(mktemp) && { cat /run/secrets/ada_deploy_key; echo; } > "$key" && chmod 600 "$key"' \
      'ssh -i "$key" -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile=/tmp/known_hosts "$@"; status=$?' \
      'rm -f "$key"; exit $status' > /usr/local/bin/ssh-ada && chmod 755 /usr/local/bin/ssh-ada
ENV GIT_SSH_COMMAND="/usr/local/bin/ssh-ada"
COPY pyproject.toml uv.lock ./
RUN --mount=type=secret,id=ada_deploy_key,required=true uv sync --frozen --no-install-project --no-dev

FROM deps AS test
RUN --mount=type=secret,id=ada_deploy_key,required=true uv sync --frozen --no-install-project
COPY src ./src
COPY tests ./tests
COPY scripts ./scripts
RUN --mount=type=secret,id=ada_deploy_key,required=true uv sync --frozen
CMD ["pytest"]

FROM deps AS runtime
COPY src ./src
RUN --mount=type=secret,id=ada_deploy_key,required=true uv sync --frozen --no-dev
ARG GLYPHH_VERSION=dev
ENV GLYPHH_VERSION=$GLYPHH_VERSION
RUN useradd --uid 1000 --create-home glyphh
USER glyphh
EXPOSE 8080
CMD ["sh", "-c", "python -m glyphh_server.db.schema && exec uvicorn glyphh_server.main:app --host 0.0.0.0 --port 8080"]
