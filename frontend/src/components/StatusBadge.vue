<script setup>
// Coloured status pill for a sample's lifecycle: queued -> running -> done | failed.
defineProps({
  status: { type: String, required: true },
})

const LABELS = {
  queued: 'En cola',
  running: 'Analizando',
  done: 'Completado',
  failed: 'Fallido',
}
</script>

<template>
  <span class="badge" :class="`status-${status}`">
    <span class="dot" />
    {{ LABELS[status] || status }}
  </span>
</template>
