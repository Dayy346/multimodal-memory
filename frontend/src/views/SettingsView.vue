<script setup lang="ts">
import { onMounted, ref } from "vue";
import {
  fetchGeminiKeyStatus,
  updateGeminiKey,
  type GeminiKeyStatus,
} from "../api";

const status = ref<GeminiKeyStatus | null>(null);
const apiKey = ref("");
const err = ref("");
const ok = ref("");
const busy = ref(false);

async function load() {
  try {
    status.value = await fetchGeminiKeyStatus();
    err.value = "";
  } catch (e) {
    err.value = String(e);
  }
}

onMounted(load);

async function saveKey() {
  err.value = "";
  ok.value = "";
  busy.value = true;
  try {
    status.value = await updateGeminiKey(apiKey.value);
    apiKey.value = "";
    ok.value = "API key saved for this server session and written to .env.";
  } catch (e) {
    err.value = String(e);
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <h1 class="page-title">Settings</h1>
  <p class="page-lead">
    Update your Gemini API key when you hit daily quota limits. Embeddings use
    the key active on the API server — not your browser.
  </p>

  <p v-if="err" class="alert-error">{{ err }}</p>
  <p v-if="ok" class="alert-success">{{ ok }}</p>

  <div class="card form-grid" style="max-width: 36rem">
    <p v-if="status?.configured" class="key-status">
      Current key: <code>{{ status.masked_key }}</code>
    </p>
    <p v-else class="key-status warn">No Gemini API key configured on the server.</p>

    <div class="field">
      <label for="geminiKey">New Gemini API key</label>
      <input
        id="geminiKey"
        v-model="apiKey"
        type="password"
        autocomplete="off"
        placeholder="AIza…"
      />
      <span class="field-hint">
        Stored as <code>GEMINI_API_KEY</code> in the server <code>.env</code> file.
      </span>
    </div>

    <button
      type="button"
      class="btn btn-primary"
      :disabled="busy || apiKey.trim().length < 8"
      @click="saveKey"
    >
      {{ busy ? "Saving…" : "Save API key" }}
    </button>
  </div>
</template>

<style scoped>
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
