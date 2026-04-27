<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { fetchJob, type Job } from "../api";

const props = defineProps<{ id: string }>();
const route = useRoute();
const router = useRouter();
const job = ref<Job | null>(null);
const err = ref("");
let timer: ReturnType<typeof setInterval> | null = null;

const jobId = () => String(props.id || route.params.id);

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
    await load();
    if (!timer) timer = setInterval(load, 2000);
  },
);

function goSearch() {
  router.push({ name: "search", query: { job: jobId() } });
}
</script>

<template>
  <h1>Job {{ jobId() }}</h1>
  <p v-if="err" style="color: #b91c1c">{{ err }}</p>
  <div v-if="job">
    <p>
      <strong>Status:</strong> {{ job.status }} — <strong>Step:</strong>
      {{ job.step }}
    </p>
    <p v-if="job.message"><strong>Message:</strong> {{ job.message }}</p>
    <p><strong>Scan root:</strong> <code>{{ job.scan_root }}</code></p>
    <p v-if="job.subpath"><strong>Subpath:</strong> {{ job.subpath }}</p>
    <pre
      v-if="job.logs?.length"
      style="
        background: #0f172a;
        color: #e2e8f0;
        padding: 1rem;
        border-radius: 8px;
        max-height: 240px;
        overflow: auto;
        font-size: 0.85rem;
      "
      >{{
        job.logs
          .slice(-40)
          .map((x) => (typeof x === "string" ? x : JSON.stringify(x)))
          .join("\n")
      }}</pre
    >
    <pre
      v-if="job.error"
      style="background: #fef2f2; color: #991b1b; padding: 1rem; border-radius: 8px"
      >{{ job.error }}</pre
    >
    <p v-if="job.status === 'completed'">
      <button type="button" @click="goSearch">Search this job</button>
    </p>
  </div>
  <p v-else>Loading…</p>
</template>
