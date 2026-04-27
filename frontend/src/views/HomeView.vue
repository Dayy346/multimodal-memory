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
const maxVideos = ref<number | null>(20);
const maxEmbedTargets = ref(200);
const chunkSeconds = ref<number | null>(null);

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
  <h1>Index a folder</h1>
  <p>
    Pick an allowed server root and optional subfolder. The API only sees paths
    listed in <code>ALLOWED_SCAN_ROOTS</code>.
  </p>
  <p v-if="err" style="color: #b91c1c">{{ err }}</p>
  <form
    @submit.prevent="start"
    style="display: grid; gap: 0.75rem; max-width: 32rem"
  >
    <label>
      Root
      <select v-model.number="rootIndex" style="width: 100%; margin-top: 0.25rem">
        <option v-for="r in roots" :key="r.index" :value="r.index">
          [{{ r.index }}] {{ r.path }}
        </option>
      </select>
    </label>
    <label>
      Subpath (under root)
      <input
        v-model="subpath"
        type="text"
        placeholder="Photos/2024"
        style="width: 100%; margin-top: 0.25rem"
      />
    </label>
    <label>
      Max files
      <input v-model.number="maxFiles" type="number" min="1" style="width: 100%; margin-top: 0.25rem" />
    </label>
    <label>
      Max videos (empty = no limit)
      <input
        v-model.number="maxVideos"
        type="number"
        min="1"
        style="width: 100%; margin-top: 0.25rem"
        placeholder="optional"
      />
    </label>
    <label>
      Max embed targets
      <input
        v-model.number="maxEmbedTargets"
        type="number"
        min="1"
        style="width: 100%; margin-top: 0.25rem"
      />
    </label>
    <label>
      Chunk seconds (optional)
      <input
        v-model.number="chunkSeconds"
        type="number"
        min="1"
        style="width: 100%; margin-top: 0.25rem"
        placeholder="default from server env"
      />
    </label>
    <button type="submit" :disabled="busy || roots.length === 0">
      {{ busy ? "Starting…" : "Start indexing job" }}
    </button>
  </form>
</template>
