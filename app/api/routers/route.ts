import { NextRequest, NextResponse } from "next/server";
import {
  discoverRouters,
  findDiscoveredRouter,
} from "@/lib/routers";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  try {
    const routers = await discoverRouters();
    const selectedAddress = request.cookies.get("ros-router")?.value;
    let selected = routers.find((router) => router.address === selectedAddress) ?? null;
    const autoSelected = !selected && routers.length === 1;
    if (autoSelected) {
      selected = routers[0];
    }

    const response = NextResponse.json({
      routers,
      selected,
      configured: Boolean(process.env.ROS_HOST?.trim()),
    });
    if (autoSelected && selected) {
      response.cookies.set("ros-router", selected.address, {
        httpOnly: true,
        sameSite: "strict",
        secure: request.nextUrl.protocol === "https:" || request.headers.get("x-forwarded-proto")?.split(",")[0] === "https",
        path: "/",
        maxAge: 60 * 60 * 24,
      });
    }
    return response;
  } catch (error) {
    const detail = error instanceof Error ? error.message : "Router discovery failed";
    return NextResponse.json({ detail }, { status: 500 });
  }
}

export async function POST(request: NextRequest) {
  let body: { macAddress?: unknown };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ detail: "Invalid JSON request body" }, { status: 400 });
  }

  if (typeof body.macAddress !== "string") {
    return NextResponse.json({ detail: "A discovered router MAC address is required" }, { status: 400 });
  }

  const router = findDiscoveredRouter(body.macAddress);
  if (!router) {
    return NextResponse.json({ detail: "That router is no longer in the discovery results. Scan again." }, { status: 404 });
  }

  const response = NextResponse.json({ selected: router });
  response.cookies.set("ros-router", router.address, {
    httpOnly: true,
    sameSite: "strict",
    secure: request.nextUrl.protocol === "https:" || request.headers.get("x-forwarded-proto")?.split(",")[0] === "https",
    path: "/",
    maxAge: 60 * 60 * 24,
  });
  return response;
}
