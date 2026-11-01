"use client";
import { useState } from "react";
import { Card, PageHeader, Badge, Toggle, Status, DataTable, Tr, Td, SearchField } from "@/components/ui";
import { rosCall, usePoll } from "@/lib/ros";
import { bytes, isTrue } from "@/lib/utils";

export default function Interfaces() {
  const ifaces = usePoll("interface", 5000);
  const addrs = usePoll("ip/address", 10000);
  const [q, setQ] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const match = (s: string[]) => s.join(" ").toLowerCase().includes(q.toLowerCase());

  async function setDisabled(id: string, disabled: boolean) {
    try { await rosCall(`interface/${id}`, "PATCH", { disabled: String(disabled) }); setErr(null); ifaces.reload(); }
    catch (e) { setErr((e as Error).message); }
  }
  async function setAddrDisabled(id: string, disabled: boolean) {
    try { await rosCall(`ip/address/${id}`, "PATCH", { disabled: String(disabled) }); setErr(null); addrs.reload(); }
    catch (e) { setErr((e as Error).message); }
  }

  const rows = (ifaces.data ?? []).filter((i) => match([i.name, i.type]));
  const ips = (addrs.data ?? []).filter((a) => match([a.address, a.interface]));

  return (
    <>
      <PageHeader title="Interfaces" subtitle="Ports, bridges and the IP addresses assigned to them"
        actions={<SearchField value={q} onChange={setQ} placeholder="Search interfaces and IPs" />} />
      {err && <Card className="mb-5 p-4 text-sm text-danger">Couldn’t save the change: {err}</Card>}

      <Card className="mb-5 overflow-hidden">
        <Status loading={ifaces.loading} error={ifaces.error} empty={rows.length ? undefined : "No interfaces match your search."}>
          <DataTable head={["Name", "Type", "Status", "Received", "Sent", "Enabled"]}>
            {rows.map((i) => {
              const off = isTrue(i.disabled);
              return (
                <Tr key={i[".id"]}>
                  <Td className="font-medium">{i.name}</Td>
                  <Td className="text-muted">{i.type}</Td>
                  <Td><Badge tone={off ? "muted" : isTrue(i.running) ? "ok" : "warn"}>{off ? "Disabled" : isTrue(i.running) ? "Up" : "No link"}</Badge></Td>
                  <Td className="tabular-nums">{bytes(i["rx-byte"])}</Td>
                  <Td className="tabular-nums">{bytes(i["tx-byte"])}</Td>
                  <Td><Toggle label={`Enable ${i.name}`} checked={!off} onCheckedChange={(v) => setDisabled(i[".id"], !v)} /></Td>
                </Tr>
              );
            })}
          </DataTable>
        </Status>
      </Card>

      <h2 className="mb-3 mt-8 text-xl font-semibold">IP addresses</h2>
      <Card className="overflow-hidden">
        <Status loading={addrs.loading} error={addrs.error} empty={ips.length ? undefined : "No IP addresses match your search."}>
          <DataTable head={["Address", "Network", "Interface", "Enabled"]}>
            {ips.map((a) => (
              <Tr key={a[".id"]}>
                <Td className="font-medium tabular-nums">{a.address}</Td>
                <Td className="tabular-nums text-muted">{a.network}</Td>
                <Td>{a.interface}</Td>
                <Td><Toggle label={`Enable ${a.address}`} checked={!isTrue(a.disabled)} onCheckedChange={(v) => setAddrDisabled(a[".id"], !v)} /></Td>
              </Tr>
            ))}
          </DataTable>
        </Status>
      </Card>
    </>
  );
}
