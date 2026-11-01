"use client";
import { useState } from "react";
import { Trash2 } from "lucide-react";
import { Card, PageHeader, Badge, Toggle, Status, DataTable, Tr, Td, SearchField, Segmented, Button } from "@/components/ui";
import { rosCall, usePoll, type Row } from "@/lib/ros";
import { bytes, isTrue } from "@/lib/utils";

const tone = (a: string) => (["accept", "masquerade", "dst-nat", "src-nat"].includes(a) ? "ok" : ["drop", "reject"].includes(a) ? "danger" : "accent") as "ok" | "danger" | "accent";

function match(r: Row) {
  const parts = [r.protocol, r["dst-port"] && `port ${r["dst-port"]}`, r["src-address"] && `from ${r["src-address"]}`,
    r["connection-state"], r["in-interface"] && `in ${r["in-interface"]}`, r["out-interface"] && `out ${r["out-interface"]}`,
    r["to-addresses"] && `to ${r["to-addresses"]}${r["to-ports"] ? ":" + r["to-ports"] : ""}`].filter(Boolean);
  return parts.length ? parts.join(" · ") : "Any traffic";
}

export default function Firewall() {
  const [tab, setTab] = useState<"filter" | "nat">("filter");
  const filter = usePoll("ip/firewall/filter", 6000);
  const nat = usePoll("ip/firewall/nat", 6000);
  const cur = tab === "filter" ? filter : nat;
  const base = `ip/firewall/${tab}`;
  const [q, setQ] = useState("");
  const [err, setErr] = useState<string | null>(null);

  const rows = (cur.data ?? []).filter((r) => [r.chain, r.action, r.comment, match(r)].join(" ").toLowerCase().includes(q.toLowerCase()));

  async function run(fn: () => Promise<unknown>) {
    try { await fn(); setErr(null); cur.reload(); } catch (e) { setErr((e as Error).message); }
  }

  return (
    <>
      <PageHeader title="Firewall" subtitle="Rules are checked from top to bottom; the first match wins"
        actions={<SearchField value={q} onChange={setQ} placeholder="Search rules" />} />
      <div className="mb-5">
        <Segmented value={tab} onChange={setTab} options={[
          { id: "filter", label: "Filter rules", count: filter.data?.length }, { id: "nat", label: "NAT rules", count: nat.data?.length }]} />
      </div>
      {err && <Card className="mb-5 p-4 text-sm text-danger">Couldn’t save the change: {err}</Card>}

      <Card className="overflow-hidden">
        <Status loading={cur.loading} error={cur.error} empty={rows.length ? undefined : q ? "No rules match your search." : "No rules yet."}>
          <DataTable head={["Chain", "Action", "Matches", "Comment", "Traffic", "Enabled", ""]}>
            {rows.map((r) => (
              <Tr key={r[".id"]} className={isTrue(r.disabled) ? "opacity-55" : ""}>
                <Td className="font-medium">{r.chain}</Td>
                <Td><Badge tone={tone(r.action)}>{r.action}</Badge></Td>
                <Td className="max-w-[22rem] truncate text-muted">{match(r)}</Td>
                <Td className="max-w-[16rem] truncate">{r.comment || <span className="text-muted">No comment</span>}</Td>
                <Td className="tabular-nums text-muted">{bytes(r.bytes)}</Td>
                <Td><Toggle label={`Enable rule ${r.comment || r[".id"]}`} checked={!isTrue(r.disabled)}
                  onCheckedChange={(v) => run(() => rosCall(`${base}/${r[".id"]}`, "PATCH", { disabled: String(!v) }))} /></Td>
                <Td><Button variant="danger" size="icon" aria-label="Delete rule"
                  onClick={() => confirm(`Delete this rule${r.comment ? ` (“${r.comment}”)` : ""}?`) && run(() => rosCall(`${base}/${r[".id"]}`, "DELETE"))}>
                  <Trash2 className="h-4 w-4" /></Button></Td>
              </Tr>
            ))}
          </DataTable>
        </Status>
      </Card>
    </>
  );
}
