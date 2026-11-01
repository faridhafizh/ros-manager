import { NextRequest, NextResponse } from "next/server";
import { mock } from "@/lib/mock";
import { isIP } from "node:net";

export const dynamic = "force-dynamic";

/** Server-side proxy: keeps router credentials out of the browser and avoids CORS. */
async function handle(req: NextRequest, { params }: { params: { path: string[] } }) {
  const { ROS_HOST, ROS_USER, ROS_PASS, ROS_SCHEME } = process.env;
  const path = params.path.join("/");
  const hasBody = !["GET", "DELETE"].includes(req.method);
  const text = hasBody ? await req.text() : undefined;
  const selectedAddress = req.cookies.get("ros-router")?.value;
  const addressParts = selectedAddress?.split(".").map(Number);
  const isPrivateAddress = isIP(selectedAddress ?? "") === 4 && addressParts !== undefined && (
    addressParts[0] === 10 ||
    (addressParts[0] === 172 && addressParts[1] >= 16 && addressParts[1] <= 31) ||
    (addressParts[0] === 192 && addressParts[1] === 168) ||
    (addressParts[0] === 169 && addressParts[1] === 254)
  );
  if (selectedAddress && !isPrivateAddress) {
    return NextResponse.json({ detail: "The selected router address must be a local IPv4 address" }, { status: 400 });
  }
  const scheme = ROS_SCHEME?.trim() || "https";
  if (selectedAddress && scheme !== "http" && scheme !== "https") {
    return NextResponse.json({ detail: "ROS_SCHEME must be either http or https" }, { status: 500 });
  }
  const host = selectedAddress ? `${scheme}://${selectedAddress}` : ROS_HOST?.trim();

  if (!host) return mock(req.method, path, text ? JSON.parse(text) : undefined);

  try {
    const res = await fetch(`${host.replace(/\/$/, "")}/rest/${path}`, {
      method: req.method, cache: "no-store", body: text || undefined,
      headers: {
        Authorization: "Basic " + Buffer.from(`${ROS_USER}:${ROS_PASS ?? ""}`).toString("base64"),
        "Content-Type": "application/json",
      },
    });
    return new NextResponse((await res.text()) || "{}", { status: res.status, headers: { "Content-Type": "application/json" } });
  } catch {
    return NextResponse.json({ detail: "The router did not respond" }, { status: 502 });
  }
}
export { handle as GET, handle as POST, handle as PATCH, handle as PUT, handle as DELETE };
