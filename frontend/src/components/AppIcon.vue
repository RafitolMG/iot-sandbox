<script setup>
// Inline SVG icons, drawn on the same 24-unit grid and stroke weight as Material Symbols
// so they sit together consistently. Inline rather than an icon font on purpose: this tool
// analyses malware and may run isolated, so it must not fetch anything from the network.
defineProps({
  name: { type: String, required: true },
  size: { type: [Number, String], default: 24 },
})
</script>

<template>
  <svg
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.7"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
    focusable="false"
  >
    <!-- mark: the emulated chip inside the isolation boundary -->
    <template v-if="name === 'mark'">
      <rect x="2.2" y="2.2" width="19.6" height="19.6" rx="5.2" stroke-width="1.5" />
      <rect x="8.6" y="8.6" width="6.8" height="6.8" rx="1.4" />
      <path d="M10.4 8.6V5.6M13.6 8.6V5.6M10.4 18.4v-3M13.6 18.4v-3" />
      <path d="M8.6 10.4h-3M8.6 13.6h-3M18.4 10.4h-3M18.4 13.6h-3" />
    </template>

    <!-- inbox: nothing collected yet -->
    <template v-else-if="name === 'inbox'">
      <path d="M4 5.5h16l1.5 8.5v3.5a2 2 0 0 1-2 2H4.5a2 2 0 0 1-2-2V14z" />
      <path d="M2.5 14h5l1.6 2.6h5.8L16.5 14h5" />
    </template>

    <!-- search-off: looked for it, it is not there -->
    <template v-else-if="name === 'search-off'">
      <circle cx="10.5" cy="10.5" r="6.3" />
      <path d="M15.2 15.2 21 21" />
      <path d="m5.5 5.5 10 10" />
    </template>
  </svg>
</template>
