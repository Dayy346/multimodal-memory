<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { createJob, fetchRoots, type RootEntry } from "../api";

const router = useRouter();
const roots = ref<RootEntry[]>([]);
const err = ref("");
const busy = ref(false);

const rootIndex = ref(0);
const subpath = ref("");
const maxFiles = ref(500);
const maxVideos = ref<number | null>(0);
const maxEmbedTargets = ref(200);
const chunkSeconds = ref<number | null>(null);
const skipThumbnails = ref(true);

onMounted(async () => {
  try {
    roots.value = await fetchRoots();
  } catch (e) {
    err.value = String(e);
  }
});

async function start() {
  err.value = "";
  busy.value = true;
  try {
    const mv =
      maxVideos.value == null || Number.isNaN(Number(maxVideos.value))
        ? null
        : maxVideos.value;
    const cs =
      chunkSeconds.value == null || Number.isNaN(Number(chunkSeconds.value))
        ? null
        : chunkSeconds.value;
    const job = await createJob({
      root_index: rootIndex.value,
      subpath: subpath.value,
      max_files: maxFiles.value,
      max_videos: mv,
      max_embed_targets: maxEmbedTargets.value,
      chunk_seconds: cs,
      skip_thumbnails: skipThumbnails.value,
    });
    await router.push({ name: "job", params: { id: job.id } });
  } catch (e) {
    err.value = String(e);
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <h1 class="page-title">Index a folder</h1>
  <p class="page-lead">
    Pick an allowed server root and optional subfolder. Paths must be listed in
    <code>ALLOWED_SCAN_ROOTS</code> on the server.
  </p>

  <p v-if="err" class="alert-error">{{ err }}</p>

  <form class="card form-grid" @submit.prevent="start">
    <div class="field">
      <label for="root">Root</label>
      <select id="root" v-model.number="rootIndex">
        <option v-for="r in roots" :key="r.index" :value="r.index">
          [{{ r.index }}] {{ r.path }}
        </option>
      </select>
    </div>
    <div class="field">
      <label for="subpath">Subpath (under root)</label>
      <input
        id="subpath"
        v-model="subpath"
        type="text"
        placeholder="library/2023/2023-07-16"
      />
    </div>
    <div class="field">
      <label for="maxFiles">Max files</label>
      <input id="maxFiles" v-model.number="maxFiles" type="number" min="1" />
    </div>
    <div class="field">
      <label for="maxVideos">Max videos (0 = photos only, skip ffmpeg)</label>
      <input
        id="maxVideos"
        v-model.number="maxVideos"
        type="number"
        min="0"
        placeholder="optional"
      />
    </div>
    <div class="field">
      <label for="maxEmbed">Max embed targets</label>
      <input
        id="maxEmbed"
        v-model.number="maxEmbedTargets"
        type="number"
        min="1"
      />
    </div>
    <div class="field">
      <label for="chunk">Chunk seconds (optional)</label>
      <input
        id="chunk"
        v-model.number="chunkSeconds"
        type="number"
        min="1"
        placeholder="server default"
      />
    </div>
    <div class="field checkbox-field">
      <label>
        <input v-model="skipThumbnails" type="checkbox" />
        Skip thumbnails (much faster for photo-only indexing)
      </label>
      <span class="field-hint">
        Thumbnails are only for search previews — embedding uses original files.
      </span>
    </div>
    <button type="submit" class="btn btn-primary" :disabled="busy || roots.length === 0">
      {{ busy ? "Starting…" : "Start indexing job" }}
    </button>
  </form>
</template>

<style scoped>
.checkbox-field label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-weight: 500;
}

.field-hint {
  display: block;
  margin-top: 0.35rem;
  font-size: 0.8rem;
  color: var(--text-muted);
}
</style>
