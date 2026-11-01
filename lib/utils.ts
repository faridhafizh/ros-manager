import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export const cn = (...i: ClassValue[]) => twMerge(clsx(i));
/** RouterOS REST returns booleans as "true"/"false" strings. */
export const isTrue = (v: unknown) => v === true || v === "true";

export function bytes(v: unknown) {
  let x = Number(v) || 0, i = 0;
  const u = ["B", "KB", "MB", "GB", "TB"];
  while (x >= 1024 && i < 4) { x /= 1024; i++; }
  return `${i === 0 || x >= 100 ? x.toFixed(0) : x.toFixed(1)} ${u[i]}`;
}
export function bits(n: number) {
  let x = n || 0, i = 0;
  const u = ["bps", "Kbps", "Mbps", "Gbps"];
  while (x >= 1000 && i < 3) { x /= 1000; i++; }
  return { value: x >= 100 || i === 0 ? x.toFixed(0) : x.toFixed(1), unit: u[i] };
}
/** "1w2d3h4m5s" -> "1w 2d" */
export function uptime(s?: string) {
  if (!s) return "–";
  const m = Array.from(s.matchAll(/(\d+)([wdhms])/g)).slice(0, 2);
  return m.map((x) => x[1] + x[2]).join(" ") || s;
}
