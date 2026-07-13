"use client";

import { Copy, Search } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ChannelStatus, Status } from "@/lib/api";

export function StatusPill({ status }: { status: Status | ChannelStatus }) {
  const styles: Record<Status | ChannelStatus, string> = {
    running: "bg-blue-400/10 text-blue-300 ring-blue-400/20", completed: "bg-emerald-400/10 text-emerald-300 ring-emerald-400/20", queued: "bg-amber-400/10 text-amber-200 ring-amber-400/20", failed: "bg-rose-400/10 text-rose-300 ring-rose-400/20", idle: "bg-zinc-500/10 text-zinc-400 ring-zinc-500/20", Active: "bg-emerald-400/10 text-emerald-300 ring-emerald-400/20", Paused: "bg-zinc-500/10 text-zinc-400 ring-zinc-500/20",
  };
  return <span className={cn("inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium capitalize ring-1", styles[status])}><i className="h-1.5 w-1.5 rounded-full bg-current" />{status}</span>;
}

export function Progress({ value }: { value: number }) { return <div aria-label={`${value}% complete`} className="h-1.5 overflow-hidden rounded-full bg-white/[.07]"><div className="h-full rounded-full bg-gradient-to-r from-blue-500 to-violet-500 transition-all duration-500" style={{ width: `${value}%` }} /></div>; }
export function SearchBox({ placeholder = "Search..." }: { placeholder?: string }) { return <label className="relative block min-w-0 flex-1"><Search className="absolute left-3 top-2.5 h-4 w-4 text-zinc-500" /><input className="input w-full pl-9" placeholder={placeholder} /></label>; }
export function CopyButton({ text }: { text: string }) { return <button type="button" onClick={() => navigator.clipboard.writeText(text)} className="rounded-lg p-2 text-zinc-500 transition hover:bg-white/[.06] hover:text-zinc-200" aria-label="Copy log line"><Copy className="h-4 w-4" /></button>; }
export function Toggle({ checked }: { checked: boolean }) { return <button type="button" aria-pressed={checked} className={cn("relative h-6 w-11 rounded-full transition", checked ? "bg-violet-500" : "bg-zinc-700")}><span className={cn("absolute top-1 h-4 w-4 rounded-full bg-white transition", checked ? "left-6" : "left-1")} /></button>; }
