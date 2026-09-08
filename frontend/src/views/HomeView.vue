<script setup>
// HomeView — dashboard: upload panel + samples table. Polls the list while any
// sample is queued/running so the analyst sees status transitions live.
import { ref, computed, onMounted, onUnmounted } from 'vue'
import UploadForm from '../components/UploadForm.vue'
import AppIcon from '../components/AppIcon.vue'
import SampleTable from '../components/SampleTable.vue'
import { listSamples } from '../api'
import { isPending } from '../format'

const POLL_MS = 3500

const samples = ref([])
const loading = ref(true)
const error = ref(null)
const lastUpdated = ref(null)
let timer = null

const anyPending = computed(() => samples.value.some((s) => isPending(s.status)))
const pendingCount = computed(() => samples.value.filter((s) => isPending(s.status)).length)

async function refresh() {
  try {
    samples.value = await listSamples()
    error.value = null
    lastUpdated.value = new Date()
  } catch (e) {
    error.value = `No se pudo cargar el listado: ${e.message}`
  } finally {
    loading.value = false
  }
  schedule()
}

// Self-rescheduling poll: only keep polling while something is in flight.
function schedule() {
  clearTimeout(timer)
  if (anyPending.value) timer = setTimeout(refresh, POLL_MS)
}

function onUploaded() {
  // A new job likely just entered the queue — refresh immediately and (re)start polling.
  refresh()
}

onMounted(refresh)
onUnmounted(() => clearTimeout(timer))
</script>

<template>
  <main class="container stack" style="gap: 24px">
    <UploadForm @uploaded="onUploaded" />

    <div class="card">
      <div class="card-head">
        <h2>Muestras</h2>
        <span class="pill">{{ samples.length }}</span>
        <span v-if="anyPending" class="row" style="gap: 6px; color: var(--run)">
          <span class="spin" />
          <span style="font-size: 0.82rem">
            {{ pendingCount }} en análisis · actualización automática
          </span>
        </span>
        <span class="spacer" />
        <button class="btn btn-ghost" :disabled="loading" @click="refresh">
          Actualizar
        </button>
      </div>

      <div v-if="error" class="card-body">
        <div class="alert alert-err">{{ error }}</div>
      </div>

      <div v-if="loading && !samples.length" class="empty">
        <span class="spin" style="width: 22px; height: 22px" />
        <p class="muted" style="margin-top: 10px">Cargando muestras…</p>
      </div>

      <div v-else-if="!samples.length" class="empty">
        <AppIcon name="inbox" :size="34" class="big" />
        <p>Aún no hay muestras. Sube un binario para lanzar el primer análisis.</p>
      </div>

      <SampleTable v-else :samples="samples" />
    </div>
  </main>
</template>
