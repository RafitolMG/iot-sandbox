// src/main.js — SPA bootstrap: Vue 3 app + router.
import { createApp } from 'vue'
import router from './router'
import App from './App.vue'
import './assets/styles.css'

createApp(App).use(router).mount('#app')
