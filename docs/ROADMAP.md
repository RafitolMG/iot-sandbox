# ROADMAP — Hitos

> Estado vivo del proyecto. Se actualiza al cerrar cada checkpoint.

## Hito 1 — MVP end-to-end con ARM ✅ COMPLETO (2026-07-07)
Flujo completo: subir binario ARM → QEMU-ARM full-system → telemetría → IoCs → web.
- CP-0 Kickoff y andamiaje ✅
- CP-1 Infraestructura levanta ✅
- CP-2 Núcleo emulación ARM ✅
- CP-3 API + cola + persistencia ✅
- CP-4 Frontend (cierre del MVP) ✅

## Hito 2 — Robustez y anti-evasión
- CP-5 INetSim / red simulada ⬜

## Hito 3 — Multi-arquitectura
- CP-6 MIPS, MIPSEL, x86_64 ⬜

## Hito 4 — Evaluación (material para el TFM)
- CP-7 Detonación de muestras reales + métricas de IoCs ⬜

---

## Mapeo a los capítulos del TFM

| Fase del proyecto | Sección del TFM (Cap. 4) |
|---|---|
| Requisitos (se consolidan en CP-0/CP-1) | 4.2.1 Identificación de requisitos |
| Diseño + implementación (CP-1 a CP-6) | 4.2.2 Descripción de la herramienta software desarrollada |
| Evaluación (CP-7) | 4.2.3 Evaluación |
