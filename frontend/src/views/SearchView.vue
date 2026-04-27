<script setup lang="ts">
import { onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { fetchJobs, runQuery, type QueryHit } from "../api";

const route = useRoute();
const jobId = ref<string | null>(null);
const jobsHint = ref("");
const q = ref("gym workout or fitness progress");
const topK = ref(12);
const hits = ref<QueryHit[]>([]);
const err = ref("");
const busy = ref(false);

async function pickDefaultJob() {
  const jid = route.query.job as string | undefined;
  if (jid) {
    jobId.value = jid;
    return;
  }
  try {
    const jobs = await fetchJobs();
    const done = jobs.find((j) => j.status === "completed");
    jobId.value = done ? done.id : null;
    jobsHint.value = done
      ? `Using latest completed job ${done.id}`
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
</script>

<template>
  <h1>Search</h1>
  <p v-if="jobsHint">{{ jobsHint }}</p>
  <form
    @submit.prevent="search"
    style="display: grid; gap: 0.75rem; max-width: 40rem"
  >
    <label>
      Job id (optional — latest completed if empty)
      <input v-model="jobId" type="text" style="width: 100%; margin-top: 0.25rem" />
    </label>
    <label>
      Query
      <input v-model="q" type="text" style="width: 100%; margin-top: 0.25rem" />
    </label>
    <label>
      Top K
      <input v-model.number="topK" type="number" min="1" max="100" style="width: 100%; margin-top: 0.25rem" />
    </label>
    <button type="submit" :disabled="busy">Search</button>
  </form>
  <p v-if="err" style="color: #b91c1c">{{ err }}</p>
  <section v-if="hits.length" style="margin-top: 1.5rem">
    <h2>Results</h2>
    <div style="display: grid; gap: 1rem">
      <article
        v-for="h in hits"
        :key="h.embed_target_id"
        style="
          border: 1px solid #e2e8f0;
          border-radius: 10px;
          padding: 0.75rem;
          background: #fff;
        "
      >
        <p>
          <strong>{{ h.modality }}</strong> · score {{ h.score.toFixed(4) }} · distance
          {{ h.distance.toFixed(4) }}
        </p>
        <p style="word-break: break-all"><code>{{ h.source_path }}</code></p>
        <p v-if="h.t_start_sec != null && h.t_end_sec != null">
          Segment: {{ h.t_start_sec }}s – {{ h.t_end_sec }}s
        </p>
        <img
          v-if="h.thumbnail_url"
          :src="h.thumbnail_url"
          alt="thumb"
          style="max-width: 100%; max-height: 220px; border-radius: 6px"
        />
        <video
          v-if="h.clip_url"
          :src="h.clip_url"
          controls
          style="max-width: 100%; max-height: 280px; border-radius: 6px"
        />
      </article>
    </div>
  </section>
</template>
