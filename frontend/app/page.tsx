"use client";

import { useQuery } from "@tanstack/react-query";
import { Activity, ArrowUpRight, CheckCircle2, Clock3, Upload } from "lucide-react";
import { ErrorState, LoadingState } from "@/components/async-state";
import { PageHeader } from "@/components/page-header";
import { Progress, StatusPill } from "@/components/ui";
import { api } from "@/lib/api";

const statIcons = { activity: Activity, check: CheckCircle2, clock: Clock3, upload: Upload } as const;
const statTones = { blue: "text-blue-300", emerald: "text-emerald-300", amber: "text-amber-200", violet: "text-violet-300" } as const;

export default function Dashboard() {
  const dashboardQuery = useQuery({ queryKey: ["dashboard"], queryFn: api.getDashboard });
  const jobsQuery = useQuery({ queryKey: ["jobs"], queryFn: api.getJobs });
  const logsQuery = useQuery({ queryKey: ["logs"], queryFn: api.getLogs });
  if (dashboardQuery.isPending || jobsQuery.isPending || logsQuery.isPending) return <LoadingState />;
  if (dashboardQuery.isError || jobsQuery.isError || logsQuery.isError) return <ErrorState onRetry={() => { void dashboardQuery.refetch(); void jobsQuery.refetch(); void logsQuery.refetch(); }} />;
  const dashboard = dashboardQuery.data;
  const runningJobs = jobsQuery.data.filter((job) => job.status === "running");

  return <>
    <PageHeader eyebrow="Overview" title={dashboard.greeting} description={dashboard.description} />
    <div className="grid gap-4 sm:grid-cols-2 2xl:grid-cols-4">
      {dashboard.stats.map((stat) => { const Icon = statIcons[stat.icon as keyof typeof statIcons]; return <div className="panel p-5" key={stat.label}><div className="flex items-start justify-between"><span className="text-sm text-zinc-500">{stat.label}</span><Icon className={`h-4 w-4 ${statTones[stat.tone as keyof typeof statTones]}`} /></div><div className="mt-5 flex items-end justify-between gap-3"><strong className="text-3xl font-semibold tracking-tight">{stat.value}</strong><span className="text-right text-xs text-zinc-500">{stat.detail}</span></div></div>; })}
    </div>
    <div className="mt-5 grid gap-5 2xl:grid-cols-3">
      <section className="panel overflow-hidden 2xl:col-span-2"><div className="flex items-center justify-between border-b border-white/[.07] px-5 py-4"><div><h2 className="text-sm font-medium">Active pipeline</h2><p className="mt-1 text-xs text-zinc-500">{runningJobs.length} jobs currently processing</p></div><button type="button" className="text-xs text-violet-300 hover:text-violet-200">View pipeline</button></div><div className="space-y-5 p-5">{runningJobs.map((job) => <div key={job.id}><div className="mb-2 flex items-center justify-between gap-4 text-sm"><span className="truncate">{job.title}<span className="ml-2 text-xs text-zinc-500">{job.stage}</span></span><span className="text-xs text-zinc-400">{job.progress}%</span></div><Progress value={job.progress} /></div>)}</div></section>
      <section className="panel p-5"><div className="flex items-center justify-between"><h2 className="text-sm font-medium">Active channels</h2><span className="text-xs text-emerald-300">{dashboard.activeChannels.filter((channel) => channel.online).length} online</span></div><div className="mt-5 space-y-4">{dashboard.activeChannels.map((channel) => <div className="flex items-center gap-3" key={channel.name}><span className="grid h-8 w-8 place-items-center rounded-lg bg-gradient-to-br from-blue-500/30 to-violet-500/30 text-xs">{channel.name[0]}</span><span className="flex-1 text-sm">{channel.name}</span><i className={`h-2 w-2 rounded-full ${channel.online ? "bg-emerald-400" : "bg-zinc-600"}`} /></div>)}</div></section>
    </div>
    <section className="panel mt-5"><div className="flex items-center justify-between border-b border-white/[.07] px-5 py-4"><div><h2 className="text-sm font-medium">Recent activity</h2><p className="mt-1 text-xs text-zinc-500">Live events from your automation system</p></div><ArrowUpRight className="h-4 w-4 text-zinc-500" /></div><div className="divide-y divide-white/[.05]">{logsQuery.data.slice(0, 4).map((log) => <div className="flex items-center gap-4 px-5 py-3" key={log.time}><StatusPill status={log.level === "ERROR" ? "failed" : log.level === "WARN" ? "queued" : "completed"} /><p className="flex-1 text-sm text-zinc-400">{log.text}</p><time className="hidden text-xs text-zinc-600 sm:block">{log.time}</time></div>)}</div></section>
  </>;
}
