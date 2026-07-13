"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Filter, Plus } from "lucide-react";
import { useState } from "react";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/page-header";
import { SearchBox, StatusPill, Toggle } from "@/components/ui";

export default function Channels() {
  const queryClient = useQueryClient();
  const { data = [] } = useQuery({ queryKey: ["channels"], queryFn: api.getChannels });
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [platform, setPlatform] = useState("YouTube");
  const [niche, setNiche] = useState("General");
  const [schedule, setSchedule] = useState("Daily");

  const createChannel = useMutation({
    mutationFn: api.createChannel,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["channels"] });
      await queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      setOpen(false);
      setName("");
      setPlatform("YouTube");
      setNiche("General");
      setSchedule("Daily");
    },
  });

  return (
    <>
      <PageHeader
        eyebrow="Publishing"
        title="Channels"
        description="Manage destinations, schedules, and publishing status."
        action={(
          <button
            type="button"
            onClick={() => setOpen((value) => !value)}
            className="inline-flex h-10 items-center gap-2 rounded-xl bg-white px-4 text-sm font-medium text-zinc-900 transition hover:bg-zinc-200"
          >
            <Plus className="h-4 w-4" />
            {open ? "Close form" : "Add channel"}
          </button>
        )}
      />

      {open && (
        <div className="panel mb-5 p-5">
          <div className="grid gap-4 md:grid-cols-2">
            <label>
              <span className="label">Name</span>
              <input className="input mt-2 w-full" value={name} onChange={(e) => setName(e.target.value)} />
            </label>
            <label>
              <span className="label">Platform</span>
              <select className="input mt-2 w-full" value={platform} onChange={(e) => setPlatform(e.target.value)}>
                <option>YouTube</option>
                <option>TikTok</option>
                <option>Instagram</option>
                <option>X</option>
              </select>
            </label>
            <label>
              <span className="label">Niche</span>
              <input className="input mt-2 w-full" value={niche} onChange={(e) => setNiche(e.target.value)} />
            </label>
            <label>
              <span className="label">Schedule</span>
              <input className="input mt-2 w-full" value={schedule} onChange={(e) => setSchedule(e.target.value)} />
            </label>
          </div>
          <div className="mt-4 flex items-center justify-between">
            <button type="button" className="inline-flex items-center gap-2 text-sm text-zinc-400" onClick={() => setOpen(false)}>
              Cancel
            </button>
            <button
              type="button"
              className="rounded-xl bg-violet-500 px-4 py-2 text-sm font-medium text-white"
              disabled={createChannel.isPending || !name.trim()}
              onClick={() =>
                createChannel.mutate({
                  name,
                  platform,
                  niche,
                  schedule,
                  is_default: data.length === 0,
                })
              }
            >
              {createChannel.isPending ? "Saving..." : "Save channel"}
            </button>
          </div>
        </div>
      )}

      <div className="mb-5 flex gap-3">
        <SearchBox placeholder="Search channels..." />
        <button className="inline-flex items-center gap-2 rounded-xl border border-white/[.08] px-3 text-sm text-zinc-400">
          <Filter className="h-4 w-4" />
          Filter
        </button>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {data.map((c) => (
          <article className="panel p-5" key={c.id}>
            <div className="flex items-start justify-between">
              <div className="flex gap-3">
                <div className="grid h-11 w-11 place-items-center rounded-xl bg-gradient-to-br from-blue-500/30 to-violet-500/30 text-sm font-semibold">
                  {c.name[0]}
                </div>
                <div>
                  <h2 className="font-medium">{c.name}</h2>
                  <p className="mt-1 text-xs text-zinc-500">{c.niche} · {c.platform}</p>
                </div>
              </div>
              <Toggle checked={c.enabled} />
            </div>
            <div className="mt-6 grid grid-cols-3 gap-3 border-t border-white/[.07] pt-4">
              <div>
                <p className="label">Status</p>
                <div className="mt-2"><StatusPill status={c.status} /></div>
              </div>
              <div>
                <p className="label">Schedule</p>
                <p className="mt-2 text-xs text-zinc-300">{c.schedule}</p>
              </div>
              <div>
                <p className="label">Published</p>
                <p className="mt-2 text-lg font-medium">{c.published}</p>
              </div>
            </div>
          </article>
        ))}
      </div>
    </>
  );
}
