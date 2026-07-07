<script setup>
// SampleTable — renders GET /samples rows; each row links to the forensic report.
import { useRouter } from 'vue-router'
import StatusBadge from './StatusBadge.vue'
import { humanBytes, fmtDate, shortHash } from '../format'

defineProps({
  samples: { type: Array, required: true },
})

const router = useRouter()
const open = (id) => router.push(`/samples/${id}`)
</script>

<template>
  <div class="table-wrap">
    <table class="data">
      <thead>
        <tr>
          <th>ID</th>
          <th>Fichero</th>
          <th>Arch</th>
          <th>sha256</th>
          <th>Tamaño</th>
          <th>Estado</th>
          <th>Subida</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="s in samples"
          :key="s.id"
          class="clickable"
          @click="open(s.id)"
        >
          <td class="mono">#{{ s.id }}</td>
          <td style="max-width: 240px; word-break: break-all">{{ s.filename }}</td>
          <td><span class="pill chip-arch">{{ s.arch }}</span></td>
          <td class="cell-mono" :title="s.sha256">{{ shortHash(s.sha256) }}</td>
          <td class="muted">{{ humanBytes(s.size_bytes) }}</td>
          <td><StatusBadge :status="s.status" /></td>
          <td class="muted" style="white-space: nowrap">{{ fmtDate(s.created_at) }}</td>
          <td>
            <RouterLink :to="`/samples/${s.id}`" @click.stop>Ver reporte →</RouterLink>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
