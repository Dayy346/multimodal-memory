<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";
import JobProgress from "../components/JobProgress.vue";
import { fetchJob, fetchJobSummary, resumeJob, type Job, type JobSummary } from "../api";

const props = defineProps<{ id: string }>();
const route = useRoute();
const router = useRouter();
const job = ref<Job | null>(null);
const summary = ref<JobSummary | null>(null);
const err = ref("");
const resumeBusy = ref(false);
const maxResumeEmbed = ref(200);
let timer: ReturnType<typeof setInterval> | null = null;

const jobId = () => String(props.id || route.params.id);

const logText = computed(() => {
  if (!job.value?.logs?.length) return "";
  return job.value.logs
    .slice(-40)
    .map((x) => (typeof x === "string" ? x : JSON.stringify(x)))
    .join("\n");
});

const isActive = computed(
  () =>
    job.value &&
    job.value.status !== "completed" &&
    job.value.status !== "failed",
);

const canResume = computed(() => {
  if (!job.value) return false;
  if (job.value.status === "failed") return true;
  if (job.value.status !== "completed") return false;
  if (!summary.value) return false;
  return summary.value.embed_target_count > summary.value.vector_count;
});

async function loadSummary() {
  try {
    summary.value = await fetchJobSummary(jobId());
  } catch {
    summary.value = null;
  }
}

async function load() {
  try {
    job.value = await fetchJob(jobId());
    err.value = "";
    if (job.value.status === "completed" || job.value.status === "failed") {
      await loadSummary();
      if (timer) {
        clearInterval(timer);
        timer = null;
      }
    }
  } catch (e) {
    err.value = String(e);
  }
}

async function continueEmbedding() {
  err.value = "";
  resumeBusy.value = true;
  try {
    job.value = await resumeJob(jobId(), {
      max_new_embed_targets: maxResumeEmbed.value,
      skip_preprocess: true,
    });
    if (timer) clearInterval(timer);
    timer = setInterval(load, 2000);
    await load();
  } catch (e) {
    err.value = String(e);
  } finally {
    resumeBusy.value = false;
  }
}

onMounted(async () => {
  await load();
  timer = setInterval(load, 2000);
});

onUnmounted(() => {
  if (timer) clearInterval(timer);
});

watch(
  () => route.params.id,
  async () => {
    if (timer) clearInterval(timer);
    timer = setInterval(load, 2000);
    await load();
  },
);

function goSearch() {
  router.push({ name: "search", query: { job: jobId() } });
}

function shortId(id: string) {
  return id.length > 12 ? `${id.slice(0, 8)}…` : id;
}
</script>

<template>
  <h1 class="page-title">Indexing job</h1>
  <p class="page-lead">
    Job <code>{{ shortId(jobId()) }}</code>
    <span v-if="isActive"> — updates every few seconds.</span>
  </p>

  <p v-if="err" class="alert-error">{{ err }}</p>

  <div v-if="job" class="card">
    <JobProgress :job="job" />

    <div class="meta-block">
      <p class="meta-row">
        <strong>Scan root</strong>
        <code>{{ job.scan_root }}</code>
      </p>
      <p v-if="job.subpath" class="meta-row">
        <strong>Subpath</strong> {{ job.subpath }}
      </p>
    </div>

    <div v-if="summary" class="summary-box">
      <p><strong>Vectors:</strong> {{ summary.vector_count }}</p>
      <p><strong>Embed targets:</strong> {{ summary.embed_target_count }}</p>
    </div>

    <div v-if="canResume" class="resume-box">
      <p class="resume-lead">
        Continue where embedding left off — skips scan/preprocess and already-indexed
        files (same <code>embed_id</code>).
      </p>
      <div class="field inline-field">
        <label for="maxResume">Max embeds this run</label>
        <input
          id="maxResume"
          v-model.number="maxResumeEmbed"
          type="number"
          min="1"
        />
      </div>
      <button
        type="button"
        class="btn btn-primary"
        :disabled="resumeBusy"
        @click="continueEmbedding"
      >
        {{ resumeBusy ? "Starting…" : "Continue embedding" }}
      </button>
    </div>

    <div v-if="job.status === 'completed' || job.status === 'failed'" class="actions">
      <button type="button" class="btn btn-primary" @click="goSearch">
        Search this library
      </button>
      <RouterLink
        :to="{ name: 'extend', query: { job: jobId() } }"
        class="btn btn-secondary"
        style="margin-left: 0.5rem"
      >
        Add more vectors
      </RouterLink>
    </div>
  </div>

  <div v-if="job?.logs?.length" class="card">
    <h2 class="section-title">Activity log</h2>
    <pre class="log-panel">{{ logText }}</pre>
  </div>

  <div v-if="job?.error" class="card">
    <h2 class="section-title">Error</h2>
    <pre class="error-panel">{{ job.error }}</pre>
  </div>

  <p v-else-if="!job && !err" class="skeleton">Loading job…</p>
</template>

<style scoped>
.meta-block {
  margin-top: 0.5rem;
  padding-top: 0.75rem;
  border-top: 1px solid var(--border);
}

.actions {
  margin-top: 1rem;
  padding-top: 0.75rem;
  border-top: 1px solid var(--border);
}

.summary-box {
  margin-top: 0.75rem;
  padding: 0.65rem 0.85rem;
  background: var(--accent-soft);
  border-radius: 8px;
  font-size: 0.9rem;
}

.summary-box p {
  margin: 0.2rem 0;
}

.resume-box {
  margin-top: 0.85rem;
  padding: 0.85rem;
  border: 1px solid #c7d2fe;
  border-radius: 8px;
  background: #eef2ff;
}

.resume-lead {
  margin: 0 0 0.65rem;
  font-size: 0.88rem;
  color: #4338ca;
}

.inline-field {
  margin-bottom: 0.65rem;
}

.inline-field label {
  display: block;
  font-size: 0.85rem;
  margin-bottom: 0.25rem;
}

.inline-field input {
  width: 8rem;
}

.section-title {
  margin: 0 0 0.65rem;
  font-size: 0.95rem;
  font-weight: 600;
  color: #475569;
}
</style>
