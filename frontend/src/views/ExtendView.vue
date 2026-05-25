<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import {
  extendJob,
  fetchJobSummary,
  fetchJobs,
  type Job,
  type JobSummary,
} from "../api";

const router = useRouter();
const jobs = ref<Job[]>([]);
const summary = ref<JobSummary | null>(null);
const err = ref("");
const busy = ref(false);

const jobId = ref("");
const maxFiles = ref(6000);
const maxVideos = ref<number | null>(null);
const maxNewEmbed = ref(200);
const chunkSeconds = ref<number | null>(null);

const selectableJobs = computed(() =>
  jobs.value.filter((j) =>
    ["completed", "failed"].includes(j.status),
  ),
);

async function loadJobs() {
  jobs.value = await fetchJobs();
}

async function loadSummary() {
  if (!jobId.value) {
    summary.value = null;
    return;
  }
  try {
    summary.value = await fetchJobSummary(jobId.value);
    err.value = "";
  } catch (e) {
    summary.value = null;
    err.value = String(e);
  }
}

onMounted(async () => {
  try {
    await loadJobs();
    const param = new URLSearchParams(window.location.search).get("job");
    if (param && selectableJobs.value.some((j) => j.id === param)) {
      jobId.value = param;
    } else if (selectableJobs.value.length > 0) {
      jobId.value = selectableJobs.value[0].id;
    }
    await loadSummary();
  } catch (e) {
    err.value = String(e);
  }
});

watch(jobId, loadSummary);

async function startExtend() {
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
    const job = await extendJob(jobId.value, {
      max_files: maxFiles.value,
      max_videos: mv,
      max_new_embed_targets: maxNewEmbed.value,
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
  <h1 class="page-title">Extend index</h1>
  <p class="page-lead">
    Add more vectors to an existing job. Files already indexed (same
    <code>embed_id</code>) are skipped — no duplicate API calls for those clips or
    images.
  </p>

  <p v-if="err" class="alert-error">{{ err }}</p>

  <form class="card form-grid" style="max-width: 36rem" @submit.prevent="startExtend">
    <div class="field">
      <label for="job">Index to extend</label>
      <select id="job" v-model="jobId" required>
        <option disabled value="">Select a job…</option>
        <option v-for="j in selectableJobs" :key="j.id" :value="j.id">
          {{ j.id.slice(0, 8) }}… — {{ j.status }} — {{ j.scan_root }}
        </option>
      </select>
    </div>

    <div v-if="summary" class="summary-box">
      <p><strong>Vectors now:</strong> {{ summary.vector_count }}</p>
      <p><strong>Embed targets:</strong> {{ summary.embed_target_count }}</p>
      <p><strong>Assets catalogued:</strong> {{ summary.asset_count }}</p>
      <p style="margin: 0; font-size: 0.85rem; color: var(--text-muted)">
        Scan root: <code>{{ summary.scan_root }}</code>
      </p>
    </div>

    <div class="field">
      <label for="maxFiles">Max files to scan</label>
      <input id="maxFiles" v-model.number="maxFiles" type="number" min="1" />
    </div>
    <div class="field">
      <label for="maxNew">Max <em>new</em> embeds this run</label>
      <input id="maxNew" v-model.number="maxNewEmbed" type="number" min="1" />
      <span class="field-hint">Stay under your daily Gemini quota (~1000 free/day).</span>
    </div>
    <div class="field">
      <label for="maxVideos">Max videos (optional)</label>
      <input
        id="maxVideos"
        v-model.number="maxVideos"
        type="number"
        min="1"
        placeholder="no limit"
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
    <button
      type="submit"
      class="btn btn-primary"
      :disabled="busy || !jobId || selectableJobs.length === 0"
    >
      {{ busy ? "Starting…" : "Add new vectors" }}
    </button>
  </form>
</template>

<style scoped>
.summary-box {
  padding: 0.75rem 1rem;
  background: var(--accent-soft);
  border-radius: 8px;
  font-size: 0.9rem;
}

.summary-box p {
  margin: 0.25rem 0;
}

.field-hint {
  display: block;
  margin-top: 0.35rem;
  font-size: 0.8rem;
  color: var(--text-muted);
}
</style>
