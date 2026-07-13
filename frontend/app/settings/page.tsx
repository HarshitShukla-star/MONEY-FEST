"use client";
import { useQuery } from "@tanstack/react-query";
import { Check, EyeOff, Save } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { Toggle } from "@/components/ui";
import { api } from "@/lib/api";

function SelectRow({ label, value, detail }: { label: string; value: string; detail: string }) {
  return <div className="flex flex-col gap-3 border-b border-white/[.06] py-5 sm:flex-row sm:items-center"><div className="flex-1"><p className="text-sm">{label}</p><p className="mt-1 text-xs text-zinc-500">{detail}</p></div><select defaultValue={value} className="input w-full sm:w-52"><option>{value}</option><option>Local provider</option><option>Not configured</option></select></div>;
}

export default function Settings() {
  const { data } = useQuery({ queryKey: ["settings"], queryFn: api.getSettings });
  if (!data) return null;
  return <><PageHeader eyebrow="Workspace" title="Settings" description="Configured from the backend." /><div className="grid gap-5 xl:grid-cols-3"><section className="panel p-5 xl:col-span-2"><h2 className="text-sm font-medium">Providers</h2><div className="mt-2">{data.providers.map((provider) => <SelectRow key={provider.label} label={provider.label} value={provider.value} detail={provider.detail} />)}</div></section><aside className="panel p-5"><h2 className="text-sm font-medium">Appearance</h2><p className="mt-1 text-xs text-zinc-500">Personalize your workspace.</p><div className="mt-6 flex items-center justify-between"><div><p className="text-sm">Dark mode</p><p className="mt-1 text-xs text-zinc-500">Always enabled</p></div><Toggle checked /></div><div className="mt-6 rounded-xl border border-violet-400/20 bg-violet-500/10 p-4"><Check className="h-4 w-4 text-violet-300" /><p className="mt-2 text-sm text-violet-100">Your configuration is synced.</p></div></aside></div><section className="panel mt-5 p-5"><div className="flex items-center justify-between"><div><h2 className="text-sm font-medium">API keys</h2><p className="mt-1 text-xs text-zinc-500">Secrets remain masked in this workspace.</p></div><button className="inline-flex items-center gap-2 rounded-xl bg-white px-3 py-2 text-xs font-medium text-zinc-900"><Save className="h-3.5 w-3.5" />Save changes</button></div><div className="mt-5 grid gap-4 md:grid-cols-2">{data.apiKeys.map((key) => <label key={key.name}><span className="label">{key.name}</span><span className="relative mt-2 block"><input readOnly value={key.configured ? "Configured" : "Not configured"} className="input w-full pr-9" /><EyeOff className="absolute right-3 top-3 h-4 w-4 text-zinc-600" /></span></label>)}</div></section></>;
}
