# docker/frontend.Dockerfile — Vue 3 + Vite SPA (CP-4).
# Multi-stage: (1) build the production bundle with Node (ADR-009: node:22-bookworm-slim),
# (2) serve the static bundle with nginx, which also reverse-proxies /api -> the FastAPI service.
# Build context is the repo root (see docker-compose.yml), so COPY paths are repo-relative.

# ── Stage 1: build the Vite bundle ─────────────────────────────────────────
FROM node:22-bookworm-slim AS build

ENV npm_config_update_notifier=false \
    npm_config_fund=false

WORKDIR /app

# Dependencies first (layer cache): reinstalled only when the lockfile changes.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

# App sources + production build (outputs to /app/dist).
COPY frontend/ ./
RUN npm run build

# ── Stage 2: serve the static bundle + proxy the API ───────────────────────
FROM nginx:1.29-alpine AS serve

# SPA-aware server config (history fallback + /api reverse proxy to api:8000).
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 5173

# nginx:alpine ships an entrypoint that launches nginx in the foreground.
