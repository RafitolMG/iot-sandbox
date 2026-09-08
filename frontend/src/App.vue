<script setup>
// Application shell: sticky top bar + routed content.
import { RouterLink, RouterView } from 'vue-router'
import AppIcon from './components/AppIcon.vue'
</script>

<template>
  <div class="app-shell">
    <header class="topbar">
      <div class="topbar-inner">
        <RouterLink to="/" class="brand">
          <AppIcon name="mark" :size="26" />
          IoT Malware Sandbox
        </RouterLink>
      </div>
    </header>

    <RouterView />
  </div>
</template>
