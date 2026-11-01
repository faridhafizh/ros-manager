"use client";
import { useEffect, useState } from "react";
import { Area, AreaChart, ResponsiveContainer, Tooltip, YAxis } from "recharts";
import { Card, PageHeader, Badge } from "@/components/ui";
import { rosCall, usePoll, type Row } from "@/lib/ros";
import { bits, bytes, isTrue, uptime } from "@/lib/utils";

type Pt = { t: number; rx: number; tx: number };

function useTraffic(iface?: string) {
  const [pts, setPts] = useState<Pt[]>([]);
  useEffect(() => {
    if (!iface) return;
    setPts([]);
    let stop = false;
    const tick = async () => {
      try {
        const [row] = await rosCall<Row[]>("interface/monitor-traffic", "POST", { interface: iface, once: "" });
        if (stop || !row) return;
        setPts((p) => [...p.slice(-39), { t: Date.now(), rx: Number(row["rx-bits-per-second"]), tx: Number(row["tx-bits-per-second"]) }]);
      } catch { /* keep last points */ }
    };
    tick();
    const id = setInterval(tick, 2000);
    return () => { stop = true; clearInterval(id); };
  }, [iface]);
  return pts;
}

function Ring({ value, label, detail }: { value: number; label: string; detail: string }) {
  const r = 34, c = 2 * Math.PI * r, v = Math.min(100, Math.max(0, value));
  const tone = v > 85 ? "text-danger" : v > 65 ? "text-warn" : "text-accent";
  return (
    <Card className="flex items-center gap-4 p-5">
      <svg viewBox="0 0 80 80" className="h-20 w-20 -rotate-90" role="img" aria-label={`${label} ${Math.round(v)} percent`}>
        <circle cx="40" cy="40" r={r} fill="none" strokeWidth="9" className="stroke-fg/10" />
        <circle cx="40" cy="40" r={r} fill="none" strokeWidth="9" strokeLinecap="round" strokeDasharray={c} strokeDashoffset={c * (1 - v / 100)}
          className={`${tone} stroke-current transition-[stroke-dashoffset] duration-700`} />
      </svg>
      <div>
        <div className="text-sm text-muted">{label}</div>
        <div className="text-2xl font-semibold tabular-nums">{Math.round(v)}%</div>
        <div className="text-xs text-muted">{detail}</div>
      </div>
    </Card>
  );
}

export default function Dashboard() {
  const res = usePoll<Row>("system/resource", 4000);
  const ifaces = usePoll("interface", 6000);
  const leases = usePoll("ip/dhcp-server/lease", 15000);
  const [sel, setSel] = useState<string>();
  const list = ifaces.data ?? [];
  const iface = sel ?? list.find((i) => isTrue(i.running) && i.type === "ether")?.name ?? list[0]?.name;
  const pts = useTraffic(iface);
  const last = pts[pts.length - 1];
  const rx = bits(last?.rx ?? 0), tx = bits(last?.tx ?? 0);
  const d = res.data;
  const mem = d ? (1 - Number(d["free-memory"]) / Number(d["total-memory"])) * 100 : 0;
  const bound = (leases.data ?? []).filter((l) => l.status === "bound").length;

  return (
    <>
      <PageHeader title="Dashboard" subtitle={d ? `${d["board-name"]} · RouterOS ${d.version}` : "Loading router details"} />
      {res.error && <Card className="mb-5 p-5 text-sm"><span className="font-medium text-danger">Can’t reach the router.</span> <span className="text-muted">{res.error}. Check ROS_HOST and credentials in .env.local.</span></Card>}

      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-4">
        <Ring value={Number(d?.["cpu-load"] ?? 0)} label="CPU" detail={d ? d["architecture-name"] : "–"} />
        <Ring value={mem} label="Memory" detail={d ? `${bytes(Number(d["total-memory"]) - Number(d["free-memory"]))} used` : "–"} />
        <Card className="p-5"><div className="text-sm text-muted">Uptime</div><div className="mt-1 text-3xl font-semibold tabular-nums">{uptime(d?.uptime)}</div><div className="mt-1 text-xs text-muted">since last reboot</div></Card>
        <Card className="p-5"><div className="text-sm text-muted">DHCP clients</div><div className="mt-1 text-3xl font-semibold tabular-nums">{bound}</div><div className="mt-1 text-xs text-muted">with an active lease</div></Card>
      </div>

      <div className="mt-5 grid grid-cols-1 gap-5 xl:grid-cols-3">
        <Card className="p-6 xl:col-span-2">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <div className="text-sm text-muted">Live traffic on {iface ?? "–"}</div>
              <div className="mt-2 flex flex-wrap gap-x-8 gap-y-1">
                <div><span className="text-5xl font-semibold tabular-nums tracking-tight text-accent">{rx.value}</span><span className="ml-1.5 text-muted">{rx.unit} down</span></div>
                <div><span className="text-5xl font-semibold tabular-nums tracking-tight text-[#AF52DE]">{tx.value}</span><span className="ml-1.5 text-muted">{tx.unit} up</span></div>
              </div>
            </div>
            <select value={iface ?? ""} onChange={(e) => setSel(e.target.value)} aria-label="Interface"
              className="glass-ctl h-10 rounded-xl px-3 text-sm outline-none">
              {list.map((i) => <option key={i[".id"]} value={i.name}>{i.name}</option>)}
            </select>
          </div>
          <div className="mt-4 h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={pts} margin={{ top: 8, right: 0, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="gr" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#0A84FF" stopOpacity=".45" /><stop offset="100%" stopColor="#0A84FF" stopOpacity="0" /></linearGradient>
                  <linearGradient id="gt" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#AF52DE" stopOpacity=".4" /><stop offset="100%" stopColor="#AF52DE" stopOpacity="0" /></linearGradient>
                </defs>
                <YAxis hide domain={[0, "auto"]} />
                <Tooltip cursor={{ stroke: "currentColor", strokeOpacity: 0.2 }} labelFormatter={() => ""}
                  formatter={(v: number, n: string) => { const b = bits(v); return [`${b.value} ${b.unit}`, n === "rx" ? "Download" : "Upload"]; }}
                  contentStyle={{ borderRadius: 12, border: "1px solid rgba(255,255,255,.3)", background: "rgba(255,255,255,.8)", backdropFilter: "blur(12px)", color: "#111", fontSize: 12 }} />
                <Area type="monotone" dataKey="rx" stroke="#0A84FF" strokeWidth={2.5} fill="url(#gr)" isAnimationActive={false} />
                <Area type="monotone" dataKey="tx" stroke="#AF52DE" strokeWidth={2.5} fill="url(#gt)" isAnimationActive={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card className="p-2">
          <div className="px-4 pb-1 pt-4 text-sm text-muted">Interfaces</div>
          <ul>
            {list.map((i) => (
              <li key={i[".id"]}>
                <button onClick={() => setSel(i.name)} className="flex w-full items-center justify-between rounded-2xl px-4 py-3 text-left transition hover:bg-white/40 dark:hover:bg-white/10">
                  <span className="flex items-center gap-3">
                    <span className={`h-2 w-2 rounded-full ${isTrue(i.disabled) ? "bg-fg/25" : isTrue(i.running) ? "bg-ok" : "bg-warn"}`} />
                    <span className="font-medium">{i.name}</span>
                  </span>
                  <Badge tone={isTrue(i.disabled) ? "muted" : isTrue(i.running) ? "ok" : "warn"}>{isTrue(i.disabled) ? "Disabled" : isTrue(i.running) ? "Up" : "No link"}</Badge>
                </button>
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </>
  );
}
