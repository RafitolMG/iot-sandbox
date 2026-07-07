// src/format.js — small presentation helpers shared across views.

/** Human-readable byte size. */
export function humanBytes(n) {
  if (n == null) return '—'
  if (n < 1024) return `${n} B`
  const units = ['KiB', 'MiB', 'GiB']
  let v = n / 1024
  let i = 0
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024
    i++
  }
  return `${v.toFixed(v < 10 ? 1 : 0)} ${units[i]}`
}

/** Locale date-time from an ISO string. */
export function fmtDate(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString('es-ES', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

/** Elapsed time between two ISO timestamps, as a compact string. */
export function fmtDuration(startIso, endIso) {
  if (!startIso || !endIso) return '—'
  const ms = new Date(endIso).getTime() - new Date(startIso).getTime()
  if (Number.isNaN(ms) || ms < 0) return '—'
  const s = ms / 1000
  if (s < 60) return `${s.toFixed(1)} s`
  const m = Math.floor(s / 60)
  return `${m} min ${Math.round(s - m * 60)} s`
}

/** Short sha256 for compact display. */
export function shortHash(h) {
  if (!h) return '—'
  return h.length > 16 ? `${h.slice(0, 10)}…${h.slice(-6)}` : h
}

/** True while the analysis is still in flight (used to drive polling). */
export function isPending(status) {
  return status === 'queued' || status === 'running'
}
