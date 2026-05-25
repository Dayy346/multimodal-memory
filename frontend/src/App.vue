<script setup lang="ts">
import { RouterLink, RouterView, useRoute } from "vue-router";

const route = useRoute();

function navClass(path: string) {
  const active =
    path === "/"
      ? route.path === "/"
      : route.path.startsWith(path);
  return active ? "nav-link active" : "nav-link";
}
</script>

<template>
  <div class="app-shell">
    <header class="app-header">
      <div class="header-inner">
        <RouterLink to="/" class="brand">Multimodal Memory</RouterLink>
        <nav class="nav">
          <RouterLink to="/" :class="navClass('/')">Index</RouterLink>
          <RouterLink to="/extend" :class="navClass('/extend')">Extend</RouterLink>
          <RouterLink to="/search" :class="navClass('/search')">Search</RouterLink>
        </nav>
      </div>
    </header>
    <main class="app-main">
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
.app-shell {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.app-header {
  background: linear-gradient(135deg, #1e1b4b 0%, #312e81 100%);
  color: #f8fafc;
  box-shadow: 0 2px 8px rgb(30 27 75 / 0.25);
}

.header-inner {
  max-width: 960px;
  margin: 0 auto;
  padding: 0.9rem 1.25rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}

.brand {
  font-weight: 700;
  font-size: 1.1rem;
  letter-spacing: -0.02em;
  color: #fff;
  text-decoration: none;
}

.brand:hover {
  text-decoration: none;
  opacity: 0.92;
}

.nav {
  display: flex;
  gap: 0.35rem;
}

.nav-link {
  color: #c7d2fe;
  padding: 0.4rem 0.75rem;
  border-radius: 8px;
  font-size: 0.9rem;
  font-weight: 500;
  text-decoration: none;
  transition: background 0.15s, color 0.15s;
}

.nav-link:hover {
  color: #fff;
  background: rgb(255 255 255 / 0.08);
  text-decoration: none;
}

.nav-link.active {
  color: #fff;
  background: rgb(255 255 255 / 0.14);
}

.app-main {
  flex: 1;
  padding: 1.5rem 1.25rem 2.5rem;
  max-width: 960px;
  margin: 0 auto;
  width: 100%;
}
</style>
