"use client";
import { useState } from "react";
import { UserX } from "lucide-react";
import { Card, PageHeader, Badge, Status, DataTable, Tr, Td, SearchField, Segmented, Button } from "@/components/ui";
import { rosCall, usePoll } from "@/lib/ros";
import { bytes, uptime } from "@/lib/utils";

type Tab = "dhcp" | "hotspot" | "pppoe";

export default function Clients() {
  const [tab, setTab] = useState<Tab>("dhcp");
  const dhcp = usePoll("ip/dhcp-server/lease", 8000);
  const hot = usePoll("ip/hotspot/active", 8000);
  const ppp = usePoll("ppp/active", 8000);
  const [q, setQ] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const f = (rows: Record<string, string>[] | null) =>
    (rows ?? []).filter((r) => Object.values(r).join(" ").toLowerCase().includes(q.toLowerCase()));

  async function disconnect(path: string, reload: () => void, who: string) {
    if (!confirm(`Disconnect ${who}? They can reconnect right away.`)) return;
    try { await rosCall(path, "DELETE"); setErr(null); reload(); } catch (e) { setErr((e as Error).message); }
  }

  const cur = tab === "dhcp" ? dhcp : tab === "hotspot" ? hot : ppp;
  const rows = f(cur.data);

  return (
    <>
      <PageHeader title="Clients" subtitle="Everyone connected through DHCP, Hotspot or PPPoE"
        actions={<SearchField value={q} onChange={setQ} placeholder="Search by name, IP or MAC" />} />
      <div className="mb-5">
        <Segmented value={tab} onChange={setTab} options={[
          { id: "dhcp", label: "DHCP leases", count: dhcp.data?.length },
          { id: "hotspot", label: "Hotspot", count: hot.data?.length },
          { id: "pppoe", label: "PPPoE", count: ppp.data?.length }]} />
      </div>
      {err && <Card className="mb-5 p-4 text-sm text-danger">Couldn’t disconnect: {err}</Card>}

      <Card className="overflow-hidden">
        <Status loading={cur.loading} error={cur.error} empty={rows.length ? undefined : q ? "No clients match your search." : "Nobody is connected here right now."}>
          {tab === "dhcp" && (
            <DataTable head={["Host", "IP address", "MAC address", "Status", "Expires in"]}>
              {rows.map((r) => (
                <Tr key={r[".id"]}>
                  <Td className="font-medium">{r["host-name"] || <span className="text-muted">Unnamed device</span>}</Td>
                  <Td className="tabular-nums">{r.address}</Td>
                  <Td className="tabular-nums text-muted">{r["mac-address"]}</Td>
                  <Td><Badge tone={r.status === "bound" ? "ok" : "warn"}>{r.status === "bound" ? "Connected" : "Waiting"}</Badge></Td>
                  <Td className="tabular-nums text-muted">{r["expires-after"] || "–"}</Td>
                </Tr>
              ))}
            </DataTable>
          )}
          {tab === "hotspot" && (
            <DataTable head={["User", "IP address", "MAC address", "Online for", "Downloaded", "Uploaded", ""]}>
              {rows.map((r) => (
                <Tr key={r[".id"]}>
                  <Td className="font-medium">{r.user}</Td>
                  <Td className="tabular-nums">{r.address}</Td>
                  <Td className="tabular-nums text-muted">{r["mac-address"]}</Td>
                  <Td className="tabular-nums">{uptime(r.uptime)}</Td>
                  <Td className="tabular-nums">{bytes(r["bytes-out"])}</Td>
                  <Td className="tabular-nums">{bytes(r["bytes-in"])}</Td>
                  <Td><Button variant="danger" size="sm" onClick={() => disconnect(`ip/hotspot/active/${r[".id"]}`, hot.reload, r.user)}><UserX className="h-4 w-4" />Disconnect</Button></Td>
                </Tr>
              ))}
            </DataTable>
          )}
          {tab === "pppoe" && (
            <DataTable head={["User", "Service", "IP address", "Caller ID", "Online for", ""]}>
              {rows.map((r) => (
                <Tr key={r[".id"]}>
                  <Td className="font-medium">{r.name}</Td>
                  <Td><Badge tone="accent">{r.service}</Badge></Td>
                  <Td className="tabular-nums">{r.address}</Td>
                  <Td className="tabular-nums text-muted">{r["caller-id"]}</Td>
                  <Td className="tabular-nums">{uptime(r.uptime)}</Td>
                  <Td><Button variant="danger" size="sm" onClick={() => disconnect(`ppp/active/${r[".id"]}`, ppp.reload, r.name)}><UserX className="h-4 w-4" />Disconnect</Button></Td>
                </Tr>
              ))}
            </DataTable>
          )}
        </Status>
      </Card>
    </>
  );
}
