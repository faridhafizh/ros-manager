import { createSocket } from "node:dgram";

export type RouterDevice = {
  address: string;
  macAddress: string;
  identity: string;
  platform: string;
  version: string;
};

const MNDP_PORT = 5678;
const DISCOVERY_TIMEOUT_MS = 2500;
let discoveredRouters: RouterDevice[] = [];

function parseMndpPacket(packet: Buffer, address: string): RouterDevice | null {
  if (packet.length < 4) return null;

  const attributes = new Map<number, Buffer>();
  let offset = 4;
  while (offset + 4 <= packet.length) {
    const type = packet.readUInt16BE(offset);
    const length = packet.readUInt16BE(offset + 2);
    offset += 4;
    if (offset + length > packet.length) return null;
    attributes.set(type, packet.subarray(offset, offset + length));
    offset += length;
  }

  const mac = attributes.get(1);
  const platform = attributes.get(8)?.toString("utf8").replace(/\0/g, "").trim() ?? "";
  if (!mac || mac.length !== 6 || !platform.toLowerCase().includes("mikrotik")) return null;

  const text = (type: number) => attributes.get(type)?.toString("utf8").replace(/\0/g, "").trim() ?? "";
  return {
    address,
    macAddress: [...mac].map((byte) => byte.toString(16).padStart(2, "0")).join(":").toUpperCase(),
    identity: text(5) || "MikroTik router",
    platform,
    version: text(7),
  };
}

export function discoverRouters(): Promise<RouterDevice[]> {
  return new Promise((resolve, reject) => {
    const socket = createSocket({ type: "udp4", reuseAddr: true });
    const routers = new Map<string, RouterDevice>();
    let bound = false;
    let settled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const finish = (error?: Error) => {
      if (settled) return;
      settled = true;
      if (timer) clearTimeout(timer);
      if (bound) socket.close();
      if (error) {
        reject(error);
        return;
      }

      discoveredRouters = [...routers.values()];
      resolve(discoveredRouters);
    };

    socket.on("error", (error) => finish(error));
    socket.on("message", (packet, remote) => {
      const router = parseMndpPacket(packet, remote.address);
      if (router) routers.set(router.macAddress, router);
    });
    socket.bind(MNDP_PORT, "0.0.0.0", () => {
      bound = true;
      socket.setBroadcast(true);
      socket.send(Buffer.from([0, 0, 0, 0]), MNDP_PORT, "255.255.255.255", (error) => {
        if (error) {
          finish(error);
          return;
        }
        timer = setTimeout(() => finish(), DISCOVERY_TIMEOUT_MS);
      });
    });
  });
}

export function findDiscoveredRouter(macAddress: string) {
  return discoveredRouters.find((item) => item.macAddress === macAddress) ?? null;
}
