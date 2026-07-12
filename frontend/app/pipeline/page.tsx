"use client";

import { useQuery } from "@tanstack/react-query";
import { Check, Circle, Loader2, XCircle } from "lucide-react";
import { ErrorState, LoadingState } from "@/components/async-state";
import { PageHeader } from "@/components/page-header";
import { Progress, StatusPill } from "@/components/ui";
import { api } from "@/lib/mock-api";

export default function Pipeline() {
  const pipelineQuery = useQuery({ queryKey: ["pipeline"], queryFn: api.getPipeline });

  if (pipelineQuery.isPending) return <LoadingState />;
  if (pipelineQuery.isError) return <ErrorState onRetry={() => void pipelineQuery.refetch()} />;

  const { job, stages } = pipelineQuery.data;

  return <>
    <PageHeader eyebrow="Automation" title="Pipeline" description="Monitor the lifecycle of your content, from trend to publish." />
    <section className="panel grid-bg overflow-hidden p-5 md:p-8">
      <div className="mb-8 flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-sm font-medium">{job.id} <span className="ml-2 text-zinc-500">{job.title}</span></p>
          <p className="mt-1 text-xs text-zinc-500">{job.started} · {job.channel}</p>
        </div>
        <StatusPill status={job.status} />
      </div>
      <div className="relative grid gap-3 md:grid-cols-7 md:gap-1">
        {stages.map((stage, index) => {
          const Icon = stage.status === "completed" ? Check : stage.status === "running" ? Loader2 : stage.status === "failed" ? XCircle : Circle;
          return <div className="relative z-10" key={stage.name}>
            <div className={`rounded-xl border p-4 ${stage.status === "running" ? "border-violet-500/50 bg-violet-500/10 shadow-glow" : "border-white/[.08] bg-zinc-900/80"}`}>
              <Icon className={`h-5 w-5 ${stage.status === "completed" ? "text-emerald-400" : stage.status === "running" ? "animate-spin text-violet-300" : "text-zinc-600"}`} />
              <p className="mt-5 text-sm font-medium leading-tight">{stage.name}</p>
              <p className="mt-2 text-xs capitalize text-zinc-500">{stage.status}</p>
              {stage.status === "running" && <div className="mt-3"><Progress value={stage.progress ?? job.progress} /></div>}
            </div>
            {index < stages.length - 1 && <div className="absolute left-[calc(50%+1.3rem)] top-9 hidden h-px w-[calc(100%-2.6rem)] bg-zinc-700 md:block" />}
          </div>;
        })}
      </div>
    </section>
    <div className="mt-5 grid gap-5 lg:grid-cols-3">
      <div className="panel p-5 lg:col-span-2">
        <h2 className="text-sm font-medium">Stage activity</h2>
        <div className="mt-5 space-y-4">
          {stages.slice(0, 4).map((stage, index) => <div className="flex items-center gap-4" key={stage.name}>
            <span className="grid h-7 w-7 place-items-center rounded-full bg-white/[.05] text-xs text-zinc-400">{index + 1}</span>
            <span className="flex-1 text-sm">{stage.name}</span>
            <span className="text-xs text-zinc-500">{stage.detail}</span>
          </div>)}
        </div>
      </div>
      <div className="panel p-5">
        <p className="label">Overall progress</p>
        <strong className="mt-2 block text-4xl font-semibold">{job.progress}%</strong>
        <div className="mt-4"><Progress value={job.progress} /></div>
        <p className="mt-4 text-xs leading-relaxed text-zinc-500">{job.eta}</p>
      </div>
    </div>
  </>;
}
