<script setup lang="ts">
import { RouterLink, RouterView } from "vue-router";
</script>

<template>
  <header
    style="
      padding: 1rem 1.25rem;
      background: #0f172a;
      color: #f8fafc;
      display: flex;
      gap: 1rem;
      align-items: center;
    "
  >
    <strong>Multimodal Memory</strong>
    <nav style="display: flex; gap: 1rem">
      <RouterLink to="/" style="color: #93c5fd">Index</RouterLink>
      <RouterLink to="/search" style="color: #93c5fd">Search</RouterLink>
    </nav>
  </header>
  <main style="padding: 1.25rem; max-width: 960px; margin: 0 auto">
    <RouterView />
  </main>
</template>
