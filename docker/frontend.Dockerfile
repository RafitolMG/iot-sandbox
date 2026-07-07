# docker/frontend.Dockerfile — PLACEHOLDER (CP-0)
# La SPA Vue 3 + Vite se implementa en CP-4.
# Imagen base propuesta en ADR-009 (docs/DECISIONS.md).
FROM node:22-bookworm-slim

WORKDIR /app

# CP-4: COPY frontend/ + npm ci + (dev) npm run dev  /  (prod) npm run build + servir.
CMD ["node", "-e", "console.log('iot-sandbox frontend: placeholder CP-0, sin implementar (ver CP-4)')"]
