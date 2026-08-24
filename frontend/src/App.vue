<script setup>
// Application shell: sticky top bar + routed content.
import { RouterLink, RouterView } from 'vue-router'
</script>

<template>
  <div class="app-shell">
    <header class="topbar">
      <div class="topbar-inner">
        <RouterLink to="/" class="brand">
          <span class="brand-mark">🛡️</span>
          <span>
            IoT Malware Sandbox
            <span class="brand-sub">· análisis dinámico multi-arquitectura</span>
          </span>
        </RouterLink>
        <span class="topbar-spacer" />
        <RouterLink to="/" class="btn btn-ghost">Muestras</RouterLink>
      </div>
    </header>

    <RouterView />

    <footer class="container" style="padding-top: 0; padding-bottom: 24px">
      <p class="faint" style="font-size: 0.8rem; text-align: center; margin: 0">
        TFM · Sandbox de análisis dinámico de malware IoT · ARM · MIPS · MIPSEL · x86_64 · detonación en QEMU
        full-system
      </p>
    </footer>
  </div>
</template>
