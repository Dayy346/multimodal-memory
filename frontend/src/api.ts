export type RootEntry = { index: number; path: string };

export type JobSummary = {
  job_id: string;
  status: string;
  scan_root: string;
  vector_count: number;
  embed_target_count: number;
  asset_count: number;
};

export type Job = {
  id: string;
  status: string;
  step: string;
  message: string | null;
  error: string | null;
  scan_root: string;
  subpath: string;
  options: Record<string, unknown>;
  logs: unknown[];
  created_at: string;
  updated_at: string;
  progress_percent: number;
  progress_label: string;
  progress_step: string;
};

export type QueryHit = {
  embed_target_id: string;
  asset_external_key: string;
  modality: string;
  source_path: string;
  path_embedded: string;
  mime_type: string;
  t_start_sec: number | null;
  t_end_sec: number | null;
  whole_source_file: boolean;
  distance: number;
  score: number;
  thumbnail_url: string | null;
  clip_url: string | null;
};

async function parseJson<T>(r: Response): Promise<T> {
  if (!r.ok) {
    const t = await r.text();
    throw new Error(t || r.statusText);
  }
  return r.json() as Promise<T>;
}

export async function fetchRoots(): Promise<RootEntry[]> {
  const r = await fetch("/api/roots");
  return parseJson<RootEntry[]>(r);
}

export async function fetchJobs(): Promise<Job[]> {
  const r = await fetch("/api/jobs");
  return parseJson<Job[]>(r);
}

export async function fetchJob(id: string): Promise<Job> {
  const r = await fetch(`/api/jobs/${id}`);
  return parseJson<Job>(r);
}

export async function fetchJobSummary(id: string): Promise<JobSummary> {
  const r = await fetch(`/api/jobs/${id}/summary`);
  return parseJson<JobSummary>(r);
}

export async function extendJob(
  jobId: string,
  body: Record<string, unknown>,
): Promise<Job> {
  const r = await fetch(`/api/jobs/${jobId}/extend`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return parseJson<Job>(r);
}

export async function resumeJob(
  jobId: string,
  body: { max_new_embed_targets?: number; skip_preprocess?: boolean } = {},
): Promise<Job> {
  const r = await fetch(`/api/jobs/${jobId}/resume`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return parseJson<Job>(r);
}

export type GeminiKeyStatus = {
  configured: boolean;
  masked_key: string | null;
};

export async function fetchGeminiKeyStatus(): Promise<GeminiKeyStatus> {
  const r = await fetch("/api/settings/gemini");
  return parseJson<GeminiKeyStatus>(r);
}

export async function updateGeminiKey(apiKey: string): Promise<GeminiKeyStatus> {
  const r = await fetch("/api/settings/gemini", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ api_key: apiKey }),
  });
  return parseJson<GeminiKeyStatus>(r);
}

export async function createJob(body: Record<string, unknown>): Promise<Job> {
  const r = await fetch("/api/jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return parseJson<Job>(r);
}

export async function runQuery(
  text: string,
  jobId: string | null | undefined,
  topK: number,
): Promise<QueryHit[]> {
  const jid =
    jobId && String(jobId).trim().length > 0 ? String(jobId).trim() : null;
  const r = await fetch("/api/query", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, job_id: jid, top_k: topK }),
  });
  return parseJson<QueryHit[]>(r);
}
