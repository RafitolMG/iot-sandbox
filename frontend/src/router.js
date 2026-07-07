// src/router.js — two views: dashboard (upload + list) and the forensic report.
import { createRouter, createWebHistory } from 'vue-router'
import HomeView from './views/HomeView.vue'
import ReportView from './views/ReportView.vue'

const routes = [
  { path: '/', name: 'home', component: HomeView },
  { path: '/samples/:id', name: 'report', component: ReportView, props: true },
]

export default createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 }),
})
