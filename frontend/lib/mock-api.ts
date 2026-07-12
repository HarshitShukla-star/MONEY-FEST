export type Status = "running" | "completed" | "queued" | "failed" | "idle";
export type ChannelStatus = "Active" | "Paused";
export type LogLevel = "INFO" | "WARN" | "ERROR" | "DEBUG";

export const channels = [
  { id: "ch_01", name: "The Growth Memo", niche: "Business", platform: "YouTube", status: "Active" as ChannelStatus, schedule: "Mon · Wed · Fri", published: 128, enabled: true },
  { id: "ch_02", name: "Mindset in Motion", niche: "Self improvement", platform: "TikTok", status: "Active" as ChannelStatus, schedule: "Daily · 9:00 AM", published: 244, enabled: true },
  { id: "ch_03", name: "Futureproof", niche: "Technology", platform: "YouTube", status: "Paused" as ChannelStatus, schedule: "Tue · Thu", published: 86, enabled: false },
  { id: "ch_04", name: "Quiet Wealth", niche: "Finance", platform: "Instagram", status: "Active" as ChannelStatus, schedule: "Daily · 6:00 PM", published: 192, enabled: true },
];

export const jobs = [
  { id: "JOB-9A2F", title: "Why most startups fail", stage: "Captions", started: "2 min ago", duration: "01:42", status: "running" as Status, progress: 68 },
  { id: "JOB-8D1C", title: "The investor mindset", stage: "Upload", started: "14 min ago", duration: "03:18", status: "running" as Status, progress: 91 },
  { id: "JOB-7BB0", title: "AI tools in 2026", stage: "Complete", started: "42 min ago", duration: "05:05", status: "completed" as Status, progress: 100 },
  { id: "JOB-6E84", title: "Build a second brain", stage: "Queue", started: "—", duration: "—", status: "queued" as Status, progress: 0 },
  { id: "JOB-5F70", title: "Money habits", stage: "Metadata", started: "1 hr ago", duration: "02:11", status: "failed" as Status, progress: 76 },
];

export const logs = [
  { time: "10:42:18", level: "INFO" as LogLevel, text: "CaptionService completed transcription for JOB-9A2F", source: "captions" },
  { time: "10:42:07", level: "INFO" as LogLevel, text: "Selected 4 candidate clips from source material", source: "clips" },
  { time: "10:41:55", level: "WARN" as LogLevel, text: "Rate limit approaching for metadata provider", source: "metadata" },
  { time: "10:39:22", level: "ERROR" as LogLevel, text: "Upload retry scheduled after provider timeout", source: "uploads" },
  { time: "10:37:10", level: "DEBUG" as LogLevel, text: "Channel ch_02 schedule resolved successfully", source: "channels" },
];

export const dashboard = {
  greeting: "Good morning, Operator.",
  description: "Here’s what your content engine is doing today.",
  stats: [
    { label: "Running jobs", value: "02", icon: "activity", detail: "Live now", tone: "blue" },
    { label: "Completed today", value: "18", icon: "check", detail: "+20% from yesterday", tone: "emerald" },
    { label: "Queue", value: "06", icon: "clock", detail: "Est. 22 min", tone: "amber" },
    { label: "Today's uploads", value: "12", icon: "upload", detail: "Across 4 channels", tone: "violet" },
  ],
  activeChannels: [
    { name: "The Growth Memo", online: true },
    { name: "Mindset in Motion", online: true },
    { name: "Futureproof", online: false },
    { name: "Quiet Wealth", online: true },
  ],
} as const;

export const pipeline = {
  job: { id: "JOB-9A2F", title: "Why most startups fail", channel: "The Growth Memo", started: "Started 2 minutes ago", status: "running" as Status, progress: 68, eta: "Expected completion in approximately 1 minute 20 seconds." },
  stages: [
    { name: "Trend Detection", status: "completed" as Status, detail: "Completed in 00:24" },
    { name: "Source Collection", status: "completed" as Status, detail: "Completed in 00:24" },
    { name: "Clip Selection", status: "completed" as Status, detail: "Completed in 00:24" },
    { name: "Captions", status: "running" as Status, detail: "Processing", progress: 68 },
    { name: "Effects", status: "idle" as Status, detail: "Waiting" },
    { name: "Metadata", status: "idle" as Status, detail: "Waiting" },
    { name: "Upload", status: "idle" as Status, detail: "Waiting" },
  ],
};

export const analytics = {
  metrics: [
    { label: "Uploads", value: "128", change: "+12.5%", icon: "uploads" },
    { label: "Views", value: "284.6K", change: "+18.2%", icon: "views" },
    { label: "Average CTR", value: "6.8%", change: "+0.9%", icon: "ctr" },
    { label: "Follower growth", value: "4,821", change: "+14.6%", icon: "growth" },
  ],
  viewTotal: "284,621 views",
  viewPoints: [38, 51, 45, 66, 57, 74, 69, 88, 83, 96, 91, 100],
  retention: { value: "54%", detail: "Up 3.2% from prior period" },
};

export const settings = {
  providers: [
    { label: "LLM provider", value: "OpenAI", detail: "Used for clip selection and metadata generation." },
    { label: "Whisper provider", value: "OpenAI Whisper", detail: "Used to create source transcriptions." },
    { label: "Upload provider", value: "YouTube", detail: "Default destination for published content." },
    { label: "Storage", value: "Local filesystem", detail: "Output clips, temporary files, and artifacts." },
  ],
  apiKeys: ["OpenAI API key", "YouTube OAuth token"],
};

// Replace these async functions with typed HTTP clients once the API layer exists.
const delay = <T,>(value: T) => new Promise<T>((resolve) => setTimeout(() => resolve(value), 250));
export const api = {
  getChannels: () => delay(channels),
  getJobs: () => delay(jobs),
  getLogs: () => delay(logs),
  getDashboard: () => delay(dashboard),
  getPipeline: () => delay(pipeline),
  getAnalytics: () => delay(analytics),
  getSettings: () => delay(settings),
};
