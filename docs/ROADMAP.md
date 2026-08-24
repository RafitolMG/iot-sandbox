# ROADMAP — Hitos

> Estado vivo del proyecto. Se actualiza al cerrar cada checkpoint.

## Hito 1 — MVP end-to-end con ARM ✅ COMPLETO (2026-07-07)
Flujo completo: subir binario ARM → QEMU-ARM full-system → telemetría → IoCs → web.
- CP-0 Kickoff y andamiaje ✅
- CP-1 Infraestructura levanta ✅
- CP-2 Núcleo emulación ARM ✅
- CP-3 API + cola + persistencia ✅
- CP-4 Frontend (cierre del MVP) ✅

## Hito 2 — Robustez y anti-evasión ✅ COMPLETO (2026-08-24)
- CP-5 INetSim / red simulada ✅ — detonación en red sin salida a Internet, con DNS comodín
  y servicios simulados; el invitado ve conectividad real y los IoCs no se contaminan.

## Hito 3 — Multi-arquitectura ✅ (2026-07-07)
- CP-6 Registro de perfiles por ISA + autodetección ELF; **ARM + MIPS + MIPSEL + x86_64**
  verificados end-to-end ✅

## Hito 4 — Evaluación (material para el TFM) ✅ COMPLETO (2026-08-24)
- CP-7 Detonación de muestras reales + métricas de IoCs ✅ — 29 muestras (Mirai/Gafgyt),
  19 detonadas en las 4 ISAs; 15 se ejecutaron. Dos defectos corregidos que solo
  aparecen con malware real.

---

## Mapeo a los capítulos del TFM

| Fase del proyecto | Sección del TFM (Cap. 4) |
|---|---|
| Requisitos (se consolidan en CP-0/CP-1) | 4.2.1 Identificación de requisitos |
| Diseño + implementación (CP-1 a CP-6) | 4.2.2 Descripción de la herramienta software desarrollada |
| Evaluación (CP-7) | 4.2.3 Evaluación |
