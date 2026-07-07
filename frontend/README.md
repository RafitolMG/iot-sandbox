# frontend/ — SPA (Vue 3 + Vite)

Single Page Application (**Vue 3.5, Composition API + Vite 6**). Permite subir una muestra,
ver el estado del análisis y visualizar el reporte forense (syscalls, flujos de red,
cambios en ficheros, IoCs).

**Estado (CP-4 · MVP completo):** implementada. Dashboard (subida + listado con polling) y
vista de reporte forense (`/samples/:id`). Cliente HTTP con `fetch` nativo (sin axios).

## Estructura

```
frontend/
├── index.html
├── package.json / package-lock.json   # deps fijadas (vue 3.5.39, vue-router 4.6.4, vite 6.4.3)
├── vite.config.js                     # build + proxy /api del dev-server
├── nginx.conf                         # sirve el bundle + reverse-proxy /api -> api:8000 (Docker)
├── .env.example                       # VITE_API_BASE / VITE_DEV_API_TARGET
└── src/
    ├── main.js · router.js · api.js · format.js
    ├── App.vue                        # shell (top bar + router-view)
    ├── assets/styles.css              # design system (tema oscuro consola forense)
    ├── components/  StatusBadge · UploadForm · SampleTable
    └── views/       HomeView (subida + listado) · ReportView (reporte forense)
```

## Cómo apunta al backend

La SPA llama al backend por la ruta base **`/api`** (variable `VITE_API_BASE`, default `/api`):

- **Docker (producción, `docker compose up`):** el bundle estático lo sirve **nginx** en el
  puerto **5173**, que además **reverse-proxya** `/api/ → http://api:8000/` (ver `nginx.conf`).
  La SPA es *same-origin* (sin CORS). Abrir **http://localhost:5173**.
- **Desarrollo local (`npm run dev`):** el **dev-server de Vite** proxya `/api` →
  `http://localhost:8000` (ver `vite.config.js`, override con `VITE_DEV_API_TARGET`). Requiere la
  API levantada aparte (`docker compose up -d db valkey api worker`).

## Comandos

```bash
npm install          # instala deps (usa package-lock.json)
npm run dev          # dev-server en http://localhost:5173 (proxy /api -> localhost:8000)
npm run build        # bundle de producción en dist/
npm run preview      # previsualiza el bundle de producción
```

Imagen base y estrategia de servido: `docker/frontend.Dockerfile` (ADR-009/019 en
`docs/DECISIONS.md`).
