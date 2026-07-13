export type Status = "running" | "completed" | "queued" | "failed" | "idle";
export type ChannelStatus = "Active" | "Paused";
export type LogLevel = "INFO" | "WARN" | "ERROR" | "DEBUG";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
export { API_BASE_URL };

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, { cache: "no-store", ...init });
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  getChannels: () => request<{
    id: string;
    name: string;
    niche: string;
    platform: string;
    status: ChannelStatus;
    schedule: string;
    published: number;
    enabled: boolean;
    is_default: boolean;
  }[]>("/channels"),
  getJobs: () => request<Array<{ id: string; title: string; stage: string; started: string; duration: string; status: Status; progress: number }>>("/jobs"),
  getLogs: () => request<Array<{ time: string; level: LogLevel; text: string; source: string }>>("/logs"),
  getDashboard: () => request<{
    greeting: string;
    description: string;
    stats: Array<{ label: string; value: string; icon: string; detail: string; tone: string }>;
    activeChannels: Array<{ name: string; online: boolean }>;
  }>("/dashboard"),
  getPipeline: () => request<{
    job: { id: string; title: string; channel: string; started: string; status: Status; progress: number; eta: string };
    stages: Array<{ name: string; status: Status; detail: string; progress?: number }>;
  }>("/pipeline"),
  getAnalytics: () => request<{
    metrics: Array<{ label: string; value: string; change: string; icon: string }>;
    viewTotal: string;
    viewPoints: number[];
    retention: { value: string; detail: string };
  }>("/analytics"),
  getSettings: () => request<{
    providers: Array<{ label: string; value: string; detail: string }>;
    apiKeys: Array<{ name: string; configured: boolean }>;
  }>("/settings"),
  createChannel: (input: { name: string; platform: string; niche: string; schedule: string; is_default: boolean }) =>
    request<{
      id: string;
      name: string;
      niche: string;
      platform: string;
      status: ChannelStatus;
      schedule: string;
      published: number;
      enabled: boolean;
      is_default: boolean;
    }>("/channels", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    }),
  submitReview: (input: { url: string; num_clips: number }) =>
    request<{ job_id: string }>("/api/review/submit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    }),
  getReviewStatus: (jobId: string) =>
    request<{
      job_id: string;
      status: string;
      progress: string;
      error: string | null;
      result: unknown | null;
      clips: Array<{
        title: string;
        start_time: number;
        end_time: number;
        score: number;
        hook_sentence: string;
        virality_reason: string;
        clip_url: string;
        approved: boolean;
        rejected: boolean;
        uploaded_url: string | null;
      }>;
    }>(`/api/review/status/${jobId}`),
  approveReviewClip: (input: { job_id: string; clip_index: number }) =>
    request<{ ok: boolean; uploaded_url?: string }>("/api/review/approve", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    }),
  rejectReviewClip: (input: { job_id: string; clip_index: number }) =>
    request<{ ok: boolean }>("/api/review/reject", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    }),
};
