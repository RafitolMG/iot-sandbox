<script setup>
// ReportView — full forensic report for one sample (GET /samples/{id}).
// Header + counters, highlighted IoCs, and tabbed telemetry (network / syscalls / fs).
// Polls while the analysis is queued/running; handles 404 and failed states.
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { RouterLink } from 'vue-router'
import StatusBadge from '../components/StatusBadge.vue'
import { getSample, ApiError } from '../api'
import { humanBytes, fmtDate, fmtDuration, isPending } from '../format'

const props = defineProps({
  id: { type: [String, Number], required: true },
})

const POLL_MS = 3000

const report = ref(null)
const loading = ref(true)
const notFound = ref(false)
const error = ref(null)
const tab = ref('iocs')
let timer = null

const counts = computed(() => report.value?.counts ?? {})
const pending = computed(() => report.value && isPending(report.value.status))
const failed = computed(() => report.value?.status === 'failed')

// `done` only means the pipeline finished, not that the sample ran: corrupt ELFs and legacy
// ABI binaries fail at execve inside the guest. Without this warning an empty report reads as
// "it did nothing" when in fact it never started.
const failedExec = computed(() =>
  (report.value?.syscalls ?? []).find((s) => s.name === 'execve' && (s.result ?? '').trim() !== '0'),
)
const didNotRun = computed(
  () =>
    report.value?.status === 'done' &&
    !(report.value?.syscalls ?? []).some((s) => s.name === 'execve' && (s.result ?? '').trim() === '0'),
)

// How many events of each kind arrived, against the real total (the API caps them).
const shown = computed(() => ({
  network: report.value?.network_flows?.length ?? 0,
  syscalls: report.value?.syscalls?.length ?? 0,
  fs: report.value?.fs_events?.length ?? 0,
}))

const TYPE_LABEL = { ip: 'IP', domain: 'Dominio', file: 'Fichero', port: 'Puerto' }

// Group IoCs by type for a scannable layout (IPs / domains first — most actionable).
const TYPE_ORDER = ['domain', 'ip', 'port', 'file']
const iocGroups = computed(() => {
  const by = {}
  for (const i of report.value?.iocs ?? []) (by[i.type] ??= []).push(i)
  return TYPE_ORDER.filter((t) => by[t]?.length).map((t) => ({ type: t, items: by[t] }))
})

const tabs = computed(() => [
  { key: 'iocs', label: 'IoCs', count: counts.value.iocs ?? 0 },
  { key: 'network', label: 'Red', count: counts.value.network_flows ?? 0 },
  { key: 'syscalls', label: 'Syscalls', count: counts.value.syscalls ?? 0 },
  { key: 'fs', label: 'Ficheros', count: counts.value.fs_events ?? 0 },
])

async function load() {
  try {
    report.value = await getSample(props.id)
    error.value = null
    notFound.value = false
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound.value = true
    else error.value = `No se pudo cargar el reporte: ${e.message}`
  } finally {
    loading.value = false
  }
  schedule()
}

function schedule() {
  clearTimeout(timer)
  if (pending.value) timer = setTimeout(load, POLL_MS)
}

onMounted(load)
onUnmounted(() => clearTimeout(timer))
</script>

<template>
  <main class="container stack" style="gap: 20px">
    <div class="row">
      <RouterLink to="/" class="btn btn-ghost">← Muestras</RouterLink>
      <span class="spacer" />
      <button v-if="report" class="btn btn-ghost" @click="load">Actualizar</button>
    </div>

    <!-- Loading / not found / hard error -->
    <div v-if="loading && !report" class="empty card">
      <span class="spin" style="width: 22px; height: 22px" />
      <p class="muted" style="margin-top: 10px">Cargando reporte…</p>
    </div>
    <div v-else-if="notFound" class="empty card">
      <div class="big">🔍</div>
      <p>No existe ninguna muestra con id <code>#{{ id }}</code>.</p>
      <RouterLink to="/">Volver al listado</RouterLink>
    </div>
    <div v-else-if="error && !report" class="card">
      <div class="card-body"><div class="alert alert-err">{{ error }}</div></div>
    </div>

    <template v-else-if="report">
      <!-- Header -->
      <div class="card">
        <div class="card-head">
          <h2 style="word-break: break-all">{{ report.filename }}</h2>
          <span class="pill chip-arch">{{ report.arch }}</span>
          <span class="spacer" />
          <StatusBadge :status="report.status" />
        </div>
        <div class="card-body stack">
          <div class="meta-grid">
            <div class="meta-item">
              <div class="k">ID</div>
              <div class="v">#{{ report.id }}</div>
            </div>
            <div class="meta-item" style="grid-column: span 2">
              <div class="k">sha256</div>
              <div class="v">{{ report.sha256 }}</div>
            </div>
            <div class="meta-item">
              <div class="k">Tamaño</div>
              <div class="v">{{ humanBytes(report.size_bytes) }}</div>
            </div>
            <div class="meta-item">
              <div class="k">Subida</div>
              <div class="v">{{ fmtDate(report.created_at) }}</div>
            </div>
            <div class="meta-item">
              <div class="k">Finalización</div>
              <div class="v">{{ fmtDate(report.finished_at) }}</div>
            </div>
            <div class="meta-item">
              <div class="k">Duración análisis</div>
              <div class="v">{{ fmtDuration(report.created_at, report.finished_at) }}</div>
            </div>
          </div>

          <!-- State banners -->
          <div v-if="pending" class="alert alert-info row" style="gap: 10px">
            <span class="spin" />
            <span>
              Análisis {{ report.status === 'queued' ? 'en cola' : 'en curso' }} — detonando la
              muestra en QEMU y recogiendo telemetría. La página se actualiza automáticamente.
            </span>
          </div>
          <div v-else-if="didNotRun" class="alert alert-warn">
            <strong>La muestra no llegó a ejecutarse en el invitado.</strong>
            <div style="margin-top: 6px">
              El análisis se completó, pero la telemetría está vacía porque
              <code>execve</code> falló<template v-if="failedExec">
                con <span class="mono">{{ failedExec.result }}</span></template>. Suele deberse a
              un ELF con cabeceras inconsistentes o compilado para una ABI que el núcleo del
              invitado no admite.
            </div>
          </div>
          <div v-else-if="failed" class="alert alert-err">
            <strong>El análisis falló.</strong>
            <div class="mono" style="margin-top: 6px; white-space: pre-wrap">
              {{ report.error || 'Sin detalle de error.' }}
            </div>
          </div>
        </div>
      </div>

      <!-- Counters -->
      <div class="grid-stats">
        <div class="stat">
          <div class="num" style="color: var(--ioc-domain)">{{ (counts.iocs ?? 0).toLocaleString('es-ES') }}</div>
          <div class="lbl">IoCs</div>
        </div>
        <div class="stat">
          <div class="num" style="color: var(--run)">{{ (counts.network_flows ?? 0).toLocaleString('es-ES') }}</div>
          <div class="lbl">Flujos de red</div>
        </div>
        <div class="stat">
          <div class="num">{{ (counts.syscalls ?? 0).toLocaleString('es-ES') }}</div>
          <div class="lbl">Syscalls</div>
        </div>
        <div class="stat">
          <div class="num" style="color: var(--ioc-file)">{{ (counts.fs_events ?? 0).toLocaleString('es-ES') }}</div>
          <div class="lbl">Eventos FS</div>
        </div>
      </div>

      <!-- Telemetry tabs -->
      <div class="card">
        <div class="tabs">
          <button
            v-for="t in tabs"
            :key="t.key"
            class="tab"
            :class="{ active: tab === t.key }"
            @click="tab = t.key"
          >
            {{ t.label }} <span class="count">{{ t.count.toLocaleString('es-ES') }}</span>
          </button>
        </div>

        <!-- IoCs -->
        <div v-if="tab === 'iocs'" class="card-body">
          <div v-if="!report.iocs.length" class="empty" style="padding: 28px">
            <span class="muted">Sin IoCs extraídos.</span>
          </div>
          <div v-else class="stack" style="gap: 20px">
            <div v-for="g in iocGroups" :key="g.type" class="stack" style="gap: 10px">
              <div class="section-title">{{ TYPE_LABEL[g.type] || g.type }} · {{ g.items.length }}</div>
              <div class="ioc-grid">
                <div v-for="(i, idx) in g.items" :key="idx" class="ioc" :data-type="i.type">
                  <div class="ioc-type">{{ TYPE_LABEL[i.type] || i.type }}</div>
                  <div class="ioc-value">{{ i.value }}</div>
                  <div class="ioc-src">
                    fuente: <span class="mono">{{ i.source || '—' }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Network -->
        <div v-if="tab === 'network'" class="card-body" style="padding: 0">
          <div v-if="shown.network < counts.network_flows" class="alert alert-info truncated">
            Mostrando los primeros {{ shown.network }} de {{ counts.network_flows }} flujos.
          </div>
          <div v-if="!report.network_flows.length" class="empty" style="padding: 28px">
            <span class="muted">Sin actividad de red capturada.</span>
          </div>
          <div v-else class="table-wrap">
            <table class="data">
              <thead>
                <tr>
                  <th>Proto</th>
                  <th>Origen</th>
                  <th>Destino</th>
                  <th>Puerto</th>
                  <th>Paquetes</th>
                  <th>Bytes</th>
                  <th>Info</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(f, i) in report.network_flows" :key="i">
                  <td><span class="proto-tag">{{ f.proto }}</span></td>
                  <td class="cell-mono">{{ f.src || '—' }}</td>
                  <td class="cell-mono">{{ f.dst || '—' }}</td>
                  <td class="mono">{{ f.dport ?? '—' }}</td>
                  <td class="muted">{{ f.packets ?? '—' }}</td>
                  <td class="muted">{{ f.bytes ?? '—' }}</td>
                  <td class="cell-mono">{{ f.info || '—' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Syscalls -->
        <div v-if="tab === 'syscalls'" class="card-body" style="padding: 0">
          <div v-if="shown.syscalls < counts.syscalls" class="alert alert-info truncated">
            Mostrando las primeras {{ shown.syscalls }} de
            {{ counts.syscalls.toLocaleString('es-ES') }} llamadas. La traza completa está en el
            artefacto <span class="mono">strace.log</span> del análisis.
          </div>
          <div v-if="!report.syscalls.length" class="empty" style="padding: 28px">
            <span class="muted">Sin syscalls registradas.</span>
          </div>
          <div v-else class="table-wrap">
            <table class="data">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Hora</th>
                  <th>Syscall</th>
                  <th>Argumentos</th>
                  <th>Resultado</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="s in report.syscalls" :key="s.seq">
                  <td class="mono faint">{{ s.seq }}</td>
                  <td class="mono faint" style="white-space: nowrap">{{ s.ts || '—' }}</td>
                  <td class="mono" style="color: var(--accent)">{{ s.name }}</td>
                  <td class="cell-mono" style="max-width: 520px">{{ s.args || '' }}</td>
                  <td class="mono muted" style="white-space: nowrap">{{ s.result || '' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- FS events -->
        <div v-if="tab === 'fs'" class="card-body" style="padding: 0">
          <div v-if="shown.fs < counts.fs_events" class="alert alert-info truncated">
            Mostrando los primeros {{ shown.fs }} de {{ counts.fs_events }} eventos.
          </div>
          <div v-if="!report.fs_events.length" class="empty" style="padding: 28px">
            <span class="muted">Sin cambios en el sistema de ficheros.</span>
          </div>
          <div v-else class="table-wrap">
            <table class="data">
              <thead>
                <tr>
                  <th>Hora</th>
                  <th>Operación</th>
                  <th>Ruta</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(e, i) in report.fs_events" :key="i">
                  <td class="mono faint" style="white-space: nowrap">{{ e.ts || '—' }}</td>
                  <td><span class="proto-tag">{{ e.op }}</span></td>
                  <td class="cell-mono">{{ e.path }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </template>
  </main>
</template>
