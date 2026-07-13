"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Loader2, X } from "lucide-react";
import { useMemo, useState } from "react";
import { API_BASE_URL, api } from "@/lib/api";
import { PageHeader } from "@/components/page-header";

type ReviewClip = Awaited<ReturnType<typeof api.getReviewStatus>>["clips"][number];

export default function ReviewPage() {
  const queryClient = useQueryClient();
  const [url, setUrl] = useState("");
  const [numClips, setNumClips] = useState(5);
  const [jobId, setJobId] = useState<string | null>(null);

  const submit = useMutation({
    mutationFn: api.submitReview,
    onSuccess: (result) => setJobId(result.job_id),
  });

  const statusQuery = useQuery({
    queryKey: ["review-status", jobId],
    queryFn: () => api.getReviewStatus(jobId ?? ""),
    enabled: Boolean(jobId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "done" || status === "error" ? false : 3000;
    },
  });

  const approve = useMutation({
    mutationFn: api.approveReviewClip,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["review-status", jobId] });
      await queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      await queryClient.invalidateQueries({ queryKey: ["channels"] });
    },
  });

  const reject = useMutation({
    mutationFn: api.rejectReviewClip,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["review-status", jobId] });
    },
  });

  const clips = statusQuery.data?.clips ?? [];
  const canShowResults = Boolean(statusQuery.data?.status === "done" && clips.length);

  return (
    <>
      <PageHeader
        eyebrow="Review"
        title="Link in, review, approve"
        description="Paste a YouTube link, generate candidate shorts, and approve the ones worth uploading."
      />
      <section className="panel p-5">
        <div className="grid gap-4 lg:grid-cols-[1fr_180px_auto]">
          <label>
            <span className="label">Source URL</span>
            <input
              className="input mt-2 w-full"
              placeholder="https://www.youtube.com/watch?v=..."
              value={url}
              onChange={(e) => setUrl(e.target.value)}
            />
          </label>
          <label>
            <span className="label">Number of clips</span>
            <input
              className="input mt-2 w-full"
              type="number"
              min={1}
              max={10}
              value={numClips}
              onChange={(e) => setNumClips(Number(e.target.value))}
            />
          </label>
          <div className="flex items-end">
            <button
              type="button"
              className="inline-flex h-12 items-center justify-center rounded-xl bg-white px-5 text-sm font-medium text-zinc-900 transition hover:bg-zinc-200 disabled:opacity-50"
              disabled={submit.isPending || !url.trim()}
              onClick={() => submit.mutate({ url, num_clips: numClips })}
            >
              {submit.isPending ? "Working..." : "Submit"}
            </button>
          </div>
        </div>
        <div className="mt-5 text-sm text-zinc-500">
          {jobId ? (
            statusQuery.data?.error ? (
              <span className="text-rose-300">{statusQuery.data.error}</span>
            ) : (
              <span>
                Job <span className="text-zinc-200">{jobId}</span> is {statusQuery.data?.status ?? "queued"}.
                {" "}{statusQuery.data?.progress}
              </span>
            )
          ) : (
            "Paste a link to start a review job."
          )}
        </div>
      </section>

      {statusQuery.isPending && jobId && (
        <div className="mt-5 panel flex items-center gap-3 p-5 text-zinc-400">
          <Loader2 className="h-5 w-5 animate-spin text-violet-300" />
          Generating candidates...
        </div>
      )}

      {canShowResults && (
        <div className="mt-5 grid gap-5 xl:grid-cols-2">
          {clips.map((clip, index) => (
            <ReviewCard
              key={`${clip.title}-${index}`}
              clip={clip}
              reviewBaseUrl={API_BASE_URL}
              onApprove={() => approve.mutate({ job_id: jobId!, clip_index: index })}
              onReject={() => reject.mutate({ job_id: jobId!, clip_index: index })}
              disabled={approve.isPending || reject.isPending}
            />
          ))}
        </div>
      )}
    </>
  );
}

function ReviewCard({
  clip,
  reviewBaseUrl,
  onApprove,
  onReject,
  disabled,
}: {
  clip: ReviewClip;
  reviewBaseUrl: string;
  onApprove: () => void;
  onReject: () => void;
  disabled: boolean;
}) {
  const src = useMemo(() => `${reviewBaseUrl}${clip.clip_url}`, [reviewBaseUrl, clip.clip_url]);

  return (
    <article className={`panel overflow-hidden ${clip.approved ? "opacity-60" : ""}`}>
      <video className="aspect-video w-full bg-black" controls src={src} />
      <div className="p-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-4xl font-semibold tracking-tight text-white">{clip.score}</p>
            <p className="mt-1 text-xs uppercase tracking-[0.2em] text-zinc-500">Virality score</p>
          </div>
          <div className="rounded-full border border-white/[.08] px-3 py-1 text-xs text-zinc-400">
            {clip.start_time.toFixed(1)}s - {clip.end_time.toFixed(1)}s
          </div>
        </div>
        <h2 className="mt-5 text-lg font-medium">{clip.title}</h2>
        <p className="mt-2 text-sm text-violet-200">{clip.hook_sentence}</p>
        <p className="mt-2 text-sm text-zinc-400">{clip.virality_reason}</p>
        <div className="mt-5 flex flex-wrap gap-3">
          <button
            type="button"
            onClick={onApprove}
            disabled={disabled || clip.approved || clip.rejected}
            className="inline-flex items-center gap-2 rounded-xl bg-emerald-500 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            <Check className="h-4 w-4" />
            {clip.uploaded_url ? "Queued" : "Approve"}
          </button>
          <button
            type="button"
            onClick={onReject}
            disabled={disabled || clip.approved || clip.rejected}
            className="inline-flex items-center gap-2 rounded-xl border border-white/[.08] px-4 py-2 text-sm text-zinc-300 disabled:opacity-50"
          >
            <X className="h-4 w-4" />
            Reject
          </button>
          {clip.uploaded_url && <span className="self-center text-sm text-emerald-300">Queued for upload</span>}
          {clip.rejected && <span className="self-center text-sm text-zinc-500">Rejected</span>}
        </div>
      </div>
    </article>
  );
}
