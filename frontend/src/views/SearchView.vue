<script setup lang="ts">
import { onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { fetchJobs, runQuery, type QueryHit } from "../api";

const route = useRoute();
const jobId = ref<string | null>(null);
const jobsHint = ref("");
const q = ref("family gathering or celebration");
const topK = ref(12);
const hits = ref<QueryHit[]>([]);
const err = ref("");
const busy = ref(false);

async function pickDefaultJob() {
  const jid = route.query.job as string | undefined;
  if (jid) {
    jobId.value = jid;
    jobsHint.value = `Searching job ${jid.slice(0, 8)}…`;
    return;
  }
  try {
    const jobs = await fetchJobs();
    const done = jobs.find((j) => j.status === "completed");
    jobId.value = done ? done.id : null;
    jobsHint.value = done
      ? `Using latest completed job (${done.id.slice(0, 8)}…)`
      : "No completed jobs yet — finish indexing first.";
  } catch (e) {
    jobsHint.value = String(e);
  }
}

onMounted(async () => {
  await pickDefaultJob();
});

watch(
  () => route.query.job,
  async () => {
    await pickDefaultJob();
  },
);

async function search() {
  err.value = "";
  busy.value = true;
  hits.value = [];
  try {
    hits.value = await runQuery(q.value, jobId.value, topK.value);
  } catch (e) {
    err.value = String(e);
  } finally {
    busy.value = false;
  }
}

function basename(path: string) {
  const parts = path.replace(/\\/g, "/").split("/");
  return parts[parts.length - 1] || path;
}
</script>

<template>
  <h1 class="page-title">Search</h1>
  <p v-if="jobsHint" class="page-lead">{{ jobsHint }}</p>

  <form class="card form-grid" style="max-width: 40rem" @submit.prevent="search">
    <div class="field">
      <label for="jobId">Job id (optional)</label>
      <input id="jobId" v-model="jobId" type="text" placeholder="latest completed if empty" />
    </div>
    <div class="field">
      <label for="query">Query</label>
      <input
        id="query"
        v-model="q"
        type="text"
        placeholder="childs birthday party"
      />
    </div>
    <div class="field">
      <label for="topK">Top K</label>
      <input id="topK" v-model.number="topK" type="number" min="1" max="100" />
    </div>
    <button type="submit" class="btn btn-primary" :disabled="busy">
      {{ busy ? "Searching…" : "Search" }}
    </button>
  </form>

  <p v-if="err" class="alert-error">{{ err }}</p>

  <section v-if="hits.length" class="results-section">
    <h2 class="section-heading">{{ hits.length }} results</h2>
    <div class="result-grid">
      <article v-for="h in hits" :key="h.embed_target_id" class="result-card">
        <header>
          <span class="chip" :class="h.modality">{{ h.modality }}</span>
          <span class="score">score {{ h.score.toFixed(3) }}</span>
        </header>
        <p class="result-path" :title="h.source_path">{{ basename(h.source_path) }}</p>
        <p v-if="h.t_start_sec != null && h.t_end_sec != null" class="result-segment">
          {{ h.t_start_sec }}s – {{ h.t_end_sec }}s
        </p>
        <img
          v-if="h.thumbnail_url"
          :src="h.thumbnail_url"
          alt=""
          class="media-preview"
        />
        <video
          v-if="h.clip_url"
          :src="h.clip_url"
          controls
          class="media-preview"
        />
      </article>
    </div>
  </section>
</template>

<style scoped>
.results-section {
  margin-top: 1.5rem;
}

.section-heading {
  margin: 0 0 1rem;
  font-size: 1.1rem;
  font-weight: 600;
}

.result-path {
  margin: 0;
  font-size: 0.9rem;
  font-weight: 500;
  word-break: break-all;
}

.result-segment {
  margin: 0.25rem 0 0;
  font-size: 0.85rem;
  color: var(--text-muted);
}
</style>
