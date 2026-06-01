<script setup lang="ts">
import { computed } from "vue";
import type { Job } from "../api";

const props = defineProps<{ job: Job }>();

const steps = [
  { id: "scan", label: "Scan" },
  { id: "preprocess", label: "Prepare" },
  { id: "embed", label: "Embed" },
  { id: "done", label: "Done" },
] as const;

const pct = computed(() =>
  Math.min(100, Math.max(0, props.job.progress_percent ?? 0)),
);

const indeterminate = computed(
  () =>
    props.job.status === "preprocessing" &&
    (props.job.progress_percent ?? 0) < 40,
);

const stepIndex = computed(() => {
  const id = props.job.progress_step || props.job.step;
  if (props.job.status === "completed" || id === "done") return 3;
  if (id === "embed" || props.job.status === "embedding") return 2;
  if (id === "preprocess" || props.job.status === "preprocessing") return 1;
  if (id === "scan" || props.job.status === "scanning") return 0;
  return 0;
});

const failStepIndex = computed(() => {
  const id = props.job.progress_step || props.job.step;
  if (id === "embed" || id === "embedding") return 2;
  if (id === "preprocess") return 1;
  if (id === "scan") return 0;
  return stepIndex.value;
});

function stepState(idx: number): "done" | "active" | "pending" | "error" {
  if (props.job.status === "failed") {
    const failAt = failStepIndex.value;
    if (idx < failAt) return "done";
    if (idx === failAt) return "error";
    return "pending";
  }
  if (idx < stepIndex.value) return "done";
  if (idx === stepIndex.value) return "active";
  return "pending";
}
</script>

<template>
  <section class="progress-panel">
    <div class="progress-header">
      <span class="progress-pct">{{ pct }}%</span>
      <span class="progress-label">{{ job.progress_label || job.message }}</span>
    </div>
    <div
      class="progress-track"
      role="progressbar"
      :aria-valuenow="pct"
      aria-valuemin="0"
      aria-valuemax="100"
    >
      <div
        class="progress-fill"
        :class="{ indeterminate }"
        :style="indeterminate ? undefined : { width: `${pct}%` }"
      />
    </div>
    <ol class="stepper">
      <li
        v-for="(s, idx) in steps"
        :key="s.id"
        class="step"
        :class="stepState(idx)"
      >
        <span class="step-dot" />
        <span class="step-label">{{ s.label }}</span>
      </li>
    </ol>
    <p class="progress-status">
      <span class="status-badge" :class="job.status">{{ job.status }}</span>
      <span v-if="job.message" class="status-msg">{{ job.message }}</span>
    </p>
  </section>
</template>
