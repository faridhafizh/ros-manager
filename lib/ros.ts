"use client";
import { useCallback, useEffect, useState } from "react";

export type Row = Record<string, string>;

/** Talks to the Next.js proxy, which forwards to the RouterOS v7 REST API. */
export async function rosCall<T = unknown>(path: string, method = "GET", body?: unknown): Promise<T> {
  const r = await fetch(`/api/ros/${path}`, {
    method, cache: "no-store",
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const j = await r.json().catch(() => null);
  if (!r.ok) throw new Error(j?.detail || j?.message || `HTTP ${r.status}`);
  return j as T;
}

export function usePoll<T = Row[]>(path: string, ms = 5000) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const reload = useCallback(async () => {
    try { setData(await rosCall<T>(path)); setError(null); }
    catch (e) { setError((e as Error).message); }
    finally { setLoading(false); }
  }, [path]);
  useEffect(() => {
    reload();
    const t = setInterval(reload, ms);
    return () => clearInterval(t);
  }, [reload, ms]);
  return { data, error, loading, reload };
}
