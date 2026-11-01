import { NextResponse } from "next/server";
type R = Record<string, string>;

const iface = (id: string, name: string, type: string, running: boolean, disabled = false, rx = 0, tx = 0): R => ({
  ".id": id, name, type, running: String(running), disabled: String(disabled), "rx-byte": String(rx), "tx-byte": String(tx),
});
const state = {
  ifaces: [
    iface("*1", "ether1", "ether", true, false, 91820394822, 12039482011),
    iface("*2", "ether2", "ether", true, false, 8120394822, 4039482011),
    iface("*3", "ether3", "ether", false, true),
    iface("*4", "ether4", "ether", false),
    iface("*5", "wlan1", "wlan", true, false, 3820394822, 9039482011),
    iface("*6", "bridge1", "bridge", true, false, 12220394822, 14039482011),
  ],
  addr: [
    { ".id": "*A", address: "203.0.113.18/30", network: "203.0.113.16", interface: "ether1", disabled: "false" },
    { ".id": "*B", address: "192.168.88.1/24", network: "192.168.88.0", interface: "bridge1", disabled: "false" },
    { ".id": "*C", address: "10.10.10.1/24", network: "10.10.10.0", interface: "wlan1", disabled: "false" },
  ] as R[],
  filter: [
    { ".id": "*10", chain: "input", action: "accept", "connection-state": "established,related", comment: "Allow established and related", disabled: "false", bytes: "48211934", packets: "61204" },
    { ".id": "*11", chain: "input", action: "drop", "connection-state": "invalid", comment: "Drop invalid", disabled: "false", bytes: "1204", packets: "22" },
    { ".id": "*12", chain: "input", action: "accept", protocol: "tcp", "dst-port": "8291", "src-address": "192.168.88.0/24", comment: "Winbox from LAN", disabled: "false", bytes: "982113", packets: "4011" },
    { ".id": "*13", chain: "input", action: "drop", "in-interface": "ether1", comment: "Drop everything else from WAN", disabled: "false", bytes: "88210", packets: "1450" },
    { ".id": "*14", chain: "forward", action: "drop", protocol: "tcp", "dst-port": "25", comment: "Block outbound SMTP", disabled: "true", bytes: "0", packets: "0" },
  ] as R[],
  nat: [
    { ".id": "*20", chain: "srcnat", action: "masquerade", "out-interface": "ether1", comment: "Share internet", disabled: "false", bytes: "3820194822", packets: "4412019" },
    { ".id": "*21", chain: "dstnat", action: "dst-nat", protocol: "tcp", "dst-port": "8080", "to-addresses": "192.168.88.20", "to-ports": "80", comment: "Web server", disabled: "false", bytes: "4812299", packets: "9810" },
  ] as R[],
  leases: [
    { ".id": "*30", address: "192.168.88.10", "mac-address": "3C:22:FB:10:A1:02", "host-name": "macbook-air", status: "bound", server: "dhcp1", "expires-after": "9m41s" },
    { ".id": "*31", address: "192.168.88.11", "mac-address": "A4:77:33:0B:19:C4", "host-name": "pixel-8", status: "bound", server: "dhcp1", "expires-after": "7m02s" },
    { ".id": "*32", address: "192.168.88.20", "mac-address": "B8:27:EB:44:90:11", "host-name": "web-server", status: "bound", server: "dhcp1", "expires-after": "9m58s" },
    { ".id": "*33", address: "192.168.88.34", "mac-address": "F0:18:98:7E:22:90", "host-name": "printer", status: "waiting", server: "dhcp1", "expires-after": "–" },
  ] as R[],
  hotspot: [
    { ".id": "*40", user: "guest-0142", address: "10.10.10.14", "mac-address": "DC:A6:32:5A:11:08", uptime: "42m10s", "bytes-in": "18340211", "bytes-out": "201983112" },
    { ".id": "*41", user: "guest-0143", address: "10.10.10.21", "mac-address": "48:2C:A0:77:F3:12", uptime: "6m55s", "bytes-in": "1220934", "bytes-out": "8211450" },
  ] as R[],
  ppp: [
    { ".id": "*50", name: "budi@isp", service: "pppoe", address: "172.16.0.2", "caller-id": "00:1B:44:11:3A:B7", uptime: "3d4h12m" },
    { ".id": "*51", name: "sari@isp", service: "pppoe", address: "172.16.0.3", "caller-id": "00:1B:44:11:3A:C9", uptime: "11h20m" },
    { ".id": "*52", name: "ahmad@isp", service: "pppoe", address: "172.16.0.4", "caller-id": "00:1B:44:11:3A:D1", uptime: "1d8h03m" },
  ] as R[],
};

export function mock(method: string, path: string, body: Record<string, string> | undefined) {
  const ok = (d: unknown) => NextResponse.json(d, { headers: { "x-ros-mode": "demo" } });
  const fail = (detail: string, status: number) => NextResponse.json({ detail }, { status });

  if (path === "system/identity") return ok({ name: "demo-router" });
  if (path === "system/resource")
    return ok({
      "board-name": "RB5009UG+S+IN", version: "7.16 (stable)", "architecture-name": "arm64",
      uptime: "12d4h31m8s", "cpu-load": String(Math.round(8 + Math.random() * 30)),
      "total-memory": "1073741824", "free-memory": String(Math.round(420e6 + Math.random() * 40e6)),
    });
  if (path === "interface/monitor-traffic") {
    const t = Date.now() / 1000, n = body?.interface ?? "";
    const rx = 18e6 + 12e6 * Math.sin(t / 7) + Math.random() * 6e6;
    const tx = 6e6 + 4e6 * Math.sin(t / 5 + 1) + Math.random() * 2e6;
    return ok([{ name: n, "rx-bits-per-second": String(Math.round(rx)), "tx-bits-per-second": String(Math.round(tx)) }]);
  }

  const lists: Record<string, R[]> = {
    interface: state.ifaces, "ip/address": state.addr, "ip/firewall/filter": state.filter, "ip/firewall/nat": state.nat,
    "ip/dhcp-server/lease": state.leases, "ip/hotspot/active": state.hotspot, "ppp/active": state.ppp,
  };
  const key = Object.keys(lists).find((k) => path === k || path.startsWith(k + "/"));
  if (!key) return fail("no such command", 404);
  const list = lists[key], id = path.slice(key.length + 1);
  if (!id) return ok(list);
  const i = list.findIndex((r) => r[".id"] === id);
  if (i < 0) return fail("no such item", 404);
  if (method === "PATCH") { Object.assign(list[i], body); return ok(list[i]); }
  if (method === "DELETE") { list.splice(i, 1); return ok({}); }
  return ok(list[i]);
}
