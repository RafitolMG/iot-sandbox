// src/api.js — thin client over the sandbox REST API (fetch native, no extra deps).
//
// Contract (backend/app/main.py + schemas.py):
//   POST /samples          multipart {file, arch}  -> 202 {sample_id, status, sha256, deduplicated}
//                          errors: 400 (arch/empty), 413 (too large)
//   GET  /samples          -> [SampleSummary]
//   GET  /samples/{id}     -> SampleReport | 404
//
// The base path (default `/api`) is proxied to the backend by Vite (dev) or nginx (Docker).

const BASE = (import.meta.env.VITE_API_BASE ?? '/api').replace(/\/$/, '')

/** Error carrying the HTTP status and the API's `detail` message when present. */
export class ApiError extends Error {
  constructor(message, status, detail) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

async function parseError(res) {
  let detail = null
  try {
    const body = await res.json()
    detail = body?.detail ?? null
  } catch {
    /* non-JSON error body */
  }
  const msg = detail || `${res.status} ${res.statusText}`
  return new ApiError(msg, res.status, detail)
}

async function getJson(path, { signal } = {}) {
  const res = await fetch(`${BASE}${path}`, { signal, headers: { Accept: 'application/json' } })
  if (!res.ok) throw await parseError(res)
  return res.json()
}


/** List all samples, most recent first. */
export function listSamples(opts) {
  return getJson('/samples', opts)
}

/** Full forensic report for one sample. */
export function getSample(id, opts) {
  return getJson(`/samples/${id}`, opts)
}

/** Upload a binary for analysis. Returns {sample_id, status, sha256, deduplicated}. */
export async function uploadSample(file, arch = 'arm') {
  const form = new FormData()
  form.append('file', file)
  form.append('arch', arch)
  const res = await fetch(`${BASE}/samples`, { method: 'POST', body: form })
  if (!res.ok) throw await parseError(res)
  return res.json()
}
