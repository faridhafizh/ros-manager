"use client";
import { useCallback, useEffect, useState } from "react";
import { ChevronDown, RefreshCw, Router, Wifi } from "lucide-react";
import { Button } from "@/components/ui";
import type { RouterDevice } from "@/lib/routers";

export function RouterPicker() {
  const [routers, setRouters] = useState<RouterDevice[]>([]);
  const [selected, setSelected] = useState<RouterDevice | null>(null);
  const [configured, setConfigured] = useState(false);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const scan = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch("/api/routers", { cache: "no-store" });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || `HTTP ${response.status}`);
      setRouters(result.routers);
      setSelected(result.selected);
      setConfigured(result.configured);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Router discovery failed");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void scan();
  }, [scan]);

  const connect = async (router: RouterDevice) => {
    setError(null);
    try {
      const response = await fetch("/api/routers", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ macAddress: router.macAddress }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || `HTTP ${response.status}`);
      setSelected(result.selected);
      setOpen(false);
      window.location.reload();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not select this router");
    }
  };

  return (
    <div className="relative">
      <Button variant="glass" onClick={() => setOpen((value) => !value)} aria-expanded={open}>
        <Router className="h-4 w-4" />
        <span className="max-w-40 truncate">{selected?.identity ?? (configured ? "Configured router" : "Find router")}</span>
        <ChevronDown className="h-4 w-4" />
      </Button>

      {open && (
        <div className="glass absolute right-0 top-12 z-30 w-80 rounded-2xl p-3 shadow-xl">
          <div className="flex items-center justify-between px-1 pb-2">
            <div className="text-sm font-medium">Nearby MikroTik routers</div>
            <button type="button" onClick={() => void scan()} disabled={loading} aria-label="Scan for routers"
              className="rounded-lg p-2 text-muted transition hover:bg-white/50 hover:text-fg disabled:opacity-50">
              <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            </button>
          </div>
          {loading && <p className="px-2 py-3 text-sm text-muted">Searching the local network…</p>}
          {!loading && routers.length === 0 && !error && (
            <p className="px-2 py-3 text-sm text-muted">No routers found. Check that neighbor discovery is enabled and the app server is on the same local network.</p>
          )}
          {error && <p role="alert" className="px-2 py-3 text-sm text-danger">{error}</p>}
          <div className="max-h-64 space-y-1 overflow-y-auto">
            {routers.map((router) => (
              <button key={router.macAddress} type="button" onClick={() => void connect(router)}
                className="flex w-full items-start gap-3 rounded-xl px-3 py-2 text-left transition hover:bg-white/50 dark:hover:bg-white/10">
                <Wifi className="mt-0.5 h-4 w-4 shrink-0 text-accent" />
                <span className="min-w-0">
                  <span className="block truncate text-sm font-medium">{router.identity}</span>
                  <span className="block truncate text-xs text-muted">{router.address} · {router.macAddress}</span>
                  <span className="block truncate text-xs text-muted">{router.platform}{router.version ? ` · ${router.version}` : ""}</span>
                </span>
              </button>
            ))}
          </div>
          {configured && <p className="mt-2 border-t border-black/5 px-2 pt-2 text-xs text-muted dark:border-white/10">A ROS_HOST value is set; selecting a detected router overrides it.</p>}
        </div>
      )}
    </div>
  );
}
