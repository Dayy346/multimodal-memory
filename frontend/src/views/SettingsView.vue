<script setup lang="ts">
import { onMounted, ref } from "vue";
import {
  fetchEmbeddingStatus,
  loadEmbeddingModel,
  type EmbeddingStatus,
} from "../api";

const status = ref<EmbeddingStatus | null>(null);
const err = ref("");
const ok = ref("");
const busy = ref(false);

async function load() {
  try {
    status.value = await fetchEmbeddingStatus();
    err.value = "";
  } catch (e) {
    err.value = String(e);
  }
}

onMounted(load);

async function warmup() {
  err.value = "";
  ok.value = "";
  busy.value = true;
  try {
    status.value = await loadEmbeddingModel();
    ok.value = status.value.loaded
      ? `Model ready on ${status.value.device}.`
      : "Load finished but the model is not marked ready.";
  } catch (e) {
    err.value = String(e);
    await load();
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <h1 class="page-title">Settings</h1>
  <p class="page-lead">
    Embeddings run locally with
    <code>jinaai/jina-embeddings-v5-omni-small</code>
    — no cloud API key. The first load downloads the weights (~4&nbsp;GB) into
    the Hugging Face cache.
  </p>

  <p v-if="err" class="alert-error">{{ err }}</p>
  <p v-if="ok" class="alert-success">{{ ok }}</p>

  <div class="card form-grid" style="max-width: 36rem">
    <dl v-if="status" class="status-grid">
      <div>
        <dt>Model</dt>
        <dd><code>{{ status.model }}</code></dd>
      </div>
      <div>
        <dt>Device</dt>
        <dd>{{ status.device }}</dd>
      </div>
      <div>
        <dt>Status</dt>
        <dd :class="status.loaded ? 'ok' : 'warn'">
          {{ status.loaded ? "Loaded" : "Not loaded yet" }}
        </dd>
      </div>
      <div>
        <dt>Vector dim</dt>
        <dd>{{ status.vector_dim }}</dd>
      </div>
      <div>
        <dt>Modality</dt>
        <dd>{{ status.modality }}</dd>
      </div>
    </dl>
    <p v-if="status?.error" class="key-status warn">{{ status.error }}</p>

    <button
      type="button"
      class="btn btn-primary"
      :disabled="busy"
      @click="warmup"
    >
      {{ busy ? "Loading model…" : status?.loaded ? "Reload model" : "Load model" }}
    </button>
    <span class="field-hint">
      First load can take several minutes. Later jobs reuse the in-memory model.
    </span>
  </div>
</template>

<style scoped>
.status-grid {
  display: grid;
  gap: 0.75rem 1rem;
  margin: 0;
}

.status-grid div {
  display: grid;
  gap: 0.15rem;
}

.status-grid dt {
  font-size: 0.75rem;
  color: var(--text-muted);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.status-grid dd {
  margin: 0;
  font-size: 0.95rem;
}

.status-grid dd.ok {
  color: #047857;
}

.status-grid dd.warn {
  color: #b45309;
}

.key-status {
  margin: 0;
  font-size: 0.9rem;
}

.key-status.warn {
  color: #b45309;
}

.field-hint {
  display: block;
  margin-top: 0.35rem;
  font-size: 0.8rem;
  color: var(--text-muted);
}

.alert-success {
  padding: 0.65rem 0.85rem;
  border-radius: 8px;
  background: #ecfdf5;
  color: #047857;
  border: 1px solid #a7f3d0;
}
</style>
