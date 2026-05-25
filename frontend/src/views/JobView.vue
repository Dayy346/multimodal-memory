<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import JobProgress from "../components/JobProgress.vue";
import { fetchJob, type Job } from "../api";

const props = defineProps<{ id: string }>();
const route = useRoute();
const router = useRouter();
const job = ref<Job | null>(null);
const err = ref("");
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

async function load() {
  try {
    job.value = await fetchJob(jobId());
    err.value = "";
    if (job.value.status === "completed" || job.value.status === "failed") {
      if (timer) {
        clearInterval(timer);
        timer = null;
      }
    }
  } catch (e) {
    err.value = String(e);
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

    <div v-if="job.status === 'completed'" class="actions">
      <button type="button" class="btn btn-primary" @click="goSearch">
        Search this library
      </button>
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

.section-title {
  margin: 0 0 0.65rem;
  font-size: 0.95rem;
  font-weight: 600;
  color: #475569;
}
</style>
