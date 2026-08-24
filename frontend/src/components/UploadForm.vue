<script setup>
// UploadForm — select a binary (+ optional arch) and POST /samples.
// Surfaces every documented outcome: accepted (202), deduplicated, 400 (arch/empty), 413 (too big).
import { ref, computed } from 'vue'
import { RouterLink } from 'vue-router'
import { uploadSample, ApiError } from '../api'
import { humanBytes } from '../format'

const emit = defineEmits(['uploaded'])

// The backend autodetects the ISA from the ELF header; picking one forces it instead.
// Each has a QEMU profile under emulation/profiles/<arch>.env.
const ARCHES = [
  { value: 'auto', label: 'Detección automática (ELF)', enabled: true },
  { value: 'arm', label: 'ARM (armhf / Cortex-A9 · vexpress-a9)', enabled: true },
  { value: 'mips', label: 'MIPS (32r2 big-endian · malta)', enabled: true },
  { value: 'mipsel', label: 'MIPSEL (32r2 little-endian · malta)', enabled: true },
  { value: 'x86_64', label: 'x86-64 (pc / virtio)', enabled: true },
]

const file = ref(null)
const arch = ref('auto')
const busy = ref(false)
const result = ref(null) // { kind: 'ok'|'dedup', sample_id, sha256 }
const error = ref(null) // string
const fileInput = ref(null)

const canSubmit = computed(() => !!file.value && !busy.value)

function onPick(e) {
  const f = e.target.files?.[0] ?? null
  file.value = f
  result.value = null
  error.value = null
}

function clearFile() {
  file.value = null
  result.value = null
  error.value = null
  if (fileInput.value) fileInput.value.value = ''
}

async function submit() {
  if (!file.value) return
  busy.value = true
  result.value = null
  error.value = null
  try {
    const res = await uploadSample(file.value, arch.value)
    result.value = {
      kind: res.deduplicated ? 'dedup' : 'ok',
      sample_id: res.sample_id,
      sha256: res.sha256,
      status: res.status,
    }
    // Reset the picker; keep the result banner. Notify the parent to refresh + poll.
    clearFileKeepResult()
    emit('uploaded', res)
  } catch (e) {
    if (e instanceof ApiError) {
      error.value =
        e.status === 413
          ? 'El fichero supera el tamaño máximo permitido (64 MiB).'
          : e.detail || e.message
    } else {
      error.value = `No se pudo contactar con la API: ${e.message}`
    }
  } finally {
    busy.value = false
  }
}

function clearFileKeepResult() {
  file.value = null
  if (fileInput.value) fileInput.value.value = ''
}
</script>

<template>
  <div class="card">
    <div class="card-head">
      <h2>Subir muestra</h2>
      <span class="spacer" />
      <span class="pill">detonación en QEMU full-system</span>
    </div>
    <div class="card-body stack">
      <div class="row" style="align-items: flex-end; gap: 16px">
        <div style="flex: 2 1 260px">
          <label class="section-title" for="file">Binario</label>
          <div class="row" style="margin-top: 6px">
            <input
              id="file"
              ref="fileInput"
              type="file"
              style="display: none"
              @change="onPick"
            />
            <button class="btn" type="button" @click="fileInput.click()">
              Seleccionar fichero…
            </button>
            <span v-if="file" class="mono muted" style="word-break: break-all">
              {{ file.name }} · {{ humanBytes(file.size) }}
              <button
                class="btn-ghost btn"
                style="padding: 2px 8px; margin-left: 6px"
                type="button"
                @click="clearFile"
              >
                ✕
              </button>
            </span>
            <span v-else class="faint">Ningún fichero seleccionado</span>
          </div>
        </div>

        <div style="flex: 1 1 200px">
          <label class="section-title" for="arch">Arquitectura</label>
          <select id="arch" v-model="arch" style="width: 100%; margin-top: 6px">
            <option
              v-for="a in ARCHES"
              :key="a.value"
              :value="a.value"
              :disabled="!a.enabled"
            >
              {{ a.label }}
            </option>
          </select>
        </div>

        <button class="btn btn-primary" :disabled="!canSubmit" @click="submit">
          <span v-if="busy" class="spin" style="margin-right: 6px" />
          {{ busy ? 'Enviando…' : 'Analizar' }}
        </button>
      </div>

      <div v-if="result?.kind === 'ok'" class="alert alert-ok">
        Muestra aceptada y encolada como
        <RouterLink :to="`/samples/${result.sample_id}`">
          <strong>#{{ result.sample_id }}</strong> </RouterLink
        >. El análisis dinámico comenzará en breve.
      </div>
      <div v-else-if="result?.kind === 'dedup'" class="alert alert-warn">
        Este binario ya existía (mismo <code>sha256</code>). Se reutiliza la muestra
        <RouterLink :to="`/samples/${result.sample_id}`"
          ><strong>#{{ result.sample_id }}</strong></RouterLink
        >
        (estado: {{ result.status }}); no se ha vuelto a encolar.
      </div>
      <div v-if="error" class="alert alert-err">{{ error }}</div>

      <p class="faint" style="font-size: 0.8rem; margin: 0">
        La muestra se trata como no confiable: se almacena por su
        <code>sha256</code> y se detona dentro de QEMU; nunca se ejecuta en el host.
      </p>
    </div>
  </div>
</template>
