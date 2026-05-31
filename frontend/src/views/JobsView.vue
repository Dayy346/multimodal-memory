<script setup lang="ts">
import { onMounted, ref } from "vue";
import { RouterLink } from "vue-router";
import { fetchJobSummary, fetchJobs, type Job, type JobSummary } from "../api";

const jobs = ref<Job[]>([]);
const summaries = ref<Record<string, JobSummary>>({});
const err = ref("");

async function load() {
  try {
    jobs.value = await fetchJobs();
    err.value = "";
    const next: Record<string, JobSummary> = {};
    await Promise.all(
      jobs.value.map(async (j) => {
        try {
          next[j.id] = await fetchJobSummary(j.id);
        } catch {
          /* ignore per-job summary errors */
        }
      }),
    );
    summaries.value = next;
  } catch (e) {
    err.value = String(e);
  }
}

onMounted(load);

function shortId(id: string) {
  return `${id.slice(0, 8)}…`;
}

function statusClass(status: string) {
  if (status === "completed") return "ok";
  if (status === "failed") return "bad";
  if (status === "preprocessing" || status === "embedding" || status === "scanning") {
    return "busy";
  }
  return "";
}
</script>

<template>
  <h1 class="page-title">All indexing jobs</h1>
  <p class="page-lead">
    Every job in the database. Stuck or running jobs only appear here — the Extend
    dropdown hides jobs that are not finished yet.
  </p>

  <p v-if="err" class="alert-error">{{ err }}</p>

  <div v-if="jobs.length === 0 && !err" class="card">
    <p>No jobs in the database. If you had a job before rebuild, the Postgres volume may have been reset.</p>
    <p style="margin-bottom: 0">
      Check on the server:
      <code>ls outputs/jobs/</code> — folders there mean job data may still exist on disk.
    </p>
  </div>

  <div v-else class="job-list">
    <article v-for="j in jobs" :key="j.id" class="card job-row">
      <div class="job-main">
        <RouterLink :to="{ name: 'job', params: { id: j.id } }" class="job-link">
          {{ shortId(j.id) }}
        </RouterLink>
        <span class="status-chip" :class="statusClass(j.status)">{{ j.status }}</span>
        <span v-if="j.step" class="step">{{ j.step }}</span>
      </div>
      <p class="scan-root"><code>{{ j.scan_root }}</code></p>
      <p v-if="summaries[j.id]" class="counts">
        {{ summaries[j.id].vector_count }} vectors ·
        {{ summaries[j.id].asset_count }} assets catalogued
      </p>
      <p v-if="j.message" class="message">{{ j.message }}</p>
      <div class="row-actions">
        <RouterLink :to="{ name: 'job', params: { id: j.id } }" class="btn btn-secondary btn-sm">
          Open job
        </RouterLink>
        <RouterLink
          v-if="j.status === 'completed'"
          :to="{ name: 'search', query: { job: j.id } }"
          class="btn btn-secondary btn-sm"
        >
          Search
        </RouterLink>
      </div>
    </article>
  </div>
</template>

<style scoped>
.job-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.job-row {
  padding: 1rem 1.1rem;
}

.job-main {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
}

.job-link {
  font-weight: 700;
  font-family: ui-monospace, monospace;
}

.status-chip {
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  padding: 0.15rem 0.45rem;
  border-radius: 6px;
  background: #e2e8f0;
  color: #475569;
}

.status-chip.ok {
  background: #d1fae5;
  color: #047857;
}

.status-chip.bad {
  background: #fee2e2;
  color: #b91c1c;
}

.status-chip.busy {
  background: #fef3c7;
  color: #b45309;
}

.step {
  font-size: 0.8rem;
  color: var(--text-muted);
}

.scan-root {
  margin: 0.4rem 0 0;
  font-size: 0.85rem;
  word-break: break-all;
}

.counts {
  margin: 0.35rem 0 0;
  font-size: 0.9rem;
}

.message {
  margin: 0.25rem 0 0;
  font-size: 0.85rem;
  color: var(--text-muted);
}

.row-actions {
  margin-top: 0.65rem;
  display: flex;
  gap: 0.5rem;
}

.btn-sm {
  padding: 0.35rem 0.65rem;
  font-size: 0.85rem;
}
</style>
