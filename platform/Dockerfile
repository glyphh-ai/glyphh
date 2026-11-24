# The platform: the built pages and the route handlers that serve them, in one Node process.

FROM node:22-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:22-slim AS runtime
WORKDIR /app
ENV NODE_ENV=production
COPY package.json package-lock.json ./
RUN npm ci --omit=dev && npm cache clean --force
COPY --from=build /app/dist ./dist
COPY demo ./demo
COPY games ./games
# demo.glyphh.ai/screener runs the Resume Screener plugin's own code (server/screener.ts): Python, the two packages it
# needs, and the plugin's skill folder from the public repo at the commit demo/screener/plugin.ref names. One source:
# nothing of the plugin is copied into this repo.
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-pip curl ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && pip3 install --no-cache-dir --break-system-packages glyphh pypdf \
    && ref="$(tr -d '[:space:]' < demo/screener/plugin.ref)" \
    && mkdir -p /opt/screener \
    && curl -fsSL "https://codeload.github.com/glyphh-ai/plugins/tar.gz/${ref}" \
       | tar -xz -C /opt/screener --strip-components=5 "plugins-${ref}/plugins/resume-screener/skills/screen-application"
USER node
EXPOSE 3000
CMD ["node", "dist/server/server/index.js"]
