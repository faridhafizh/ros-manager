"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTheme } from "next-themes";
import { LayoutDashboard, Network, Shield, Users, Moon, Sun, Router } from "lucide-react";
import { cn } from "@/lib/utils";
import { RouterPicker } from "@/components/router-picker";

const nav = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/interfaces", label: "Interfaces", icon: Network },
  { href: "/firewall", label: "Firewall", icon: Shield },
  { href: "/clients", label: "Clients", icon: Users },
];

function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  const dark = mounted && resolvedTheme === "dark";
  return (
    <button onClick={() => setTheme(dark ? "light" : "dark")} aria-label="Toggle light and dark theme"
      className="glass-ctl grid h-10 w-10 place-items-center rounded-xl transition active:scale-95">
      {dark ? <Sun className="h-[18px] w-[18px]" /> : <Moon className="h-[18px] w-[18px]" />}
    </button>
  );
}

function useRouterInfo() {
  const [info, setInfo] = useState<{ name: string; demo: boolean; online: boolean } | null>(null);
  useEffect(() => {
    let stop = false;
    const load = async () => {
      try {
        const r = await fetch("/api/ros/system/identity", { cache: "no-store" });
        const j = await r.json();
        if (!stop) setInfo(r.ok ? { name: j.name, demo: r.headers.get("x-ros-mode") === "demo", online: true } : { name: "Router", demo: false, online: false });
      } catch { if (!stop) setInfo({ name: "Router", demo: false, online: false }); }
    };
    load();
    const t = setInterval(load, 15000);
    return () => { stop = true; clearInterval(t); };
  }, []);
  return info;
}

export function Shell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const info = useRouterInfo();
  const active = (h: string) => (h === "/" ? path === "/" : path.startsWith(h));

  return (
    <div className="mx-auto flex min-h-screen max-w-[1400px] gap-5 p-4 md:p-5">
      <aside className="glass sticky top-5 hidden h-[calc(100vh-2.5rem)] w-60 shrink-0 flex-col rounded-[28px] p-4 md:flex">
        <div className="flex items-center gap-3 px-2 py-3">
          <div className="grid h-10 w-10 place-items-center rounded-xl bg-accent text-white"><Router className="h-5 w-5" /></div>
          <div className="font-semibold leading-tight">ROS Manager<div className="text-xs font-normal text-muted">RouterOS v7</div></div>
        </div>
        <nav className="mt-4 flex flex-col gap-1">
          {nav.map(({ href, label, icon: Icon }) => (
            <Link key={href} href={href} aria-current={active(href) ? "page" : undefined}
              className={cn("flex h-11 items-center gap-3 rounded-xl px-3 text-[15px] font-medium transition",
                active(href) ? "bg-accent text-white shadow-lg shadow-accent/30" : "text-muted hover:bg-white/40 hover:text-fg dark:hover:bg-white/10")}>
              <Icon className="h-[18px] w-[18px]" />{label}
            </Link>
          ))}
        </nav>
        <div className="glass-ctl mt-auto rounded-2xl p-3 text-sm">
          <div className="flex items-center gap-2 font-medium">
            <span className={cn("h-2 w-2 rounded-full", info?.online ? "bg-ok" : "bg-danger")} />
            {info?.name ?? "Connecting…"}
          </div>
          <div className="mt-0.5 text-xs text-muted">{info ? (info.online ? (info.demo ? "Showing demo data" : "Connected") : "Offline") : " "}</div>
        </div>
      </aside>

      <main className="min-w-0 flex-1 pb-24 md:pb-6">
        <div className="mb-4 flex justify-end gap-2"><RouterPicker /><ThemeToggle /></div>
        {children}
      </main>

      <nav className="glass fixed inset-x-4 bottom-4 z-20 flex justify-around rounded-[24px] p-1.5 md:hidden">
        {nav.map(({ href, label, icon: Icon }) => (
          <Link key={href} href={href} aria-current={active(href) ? "page" : undefined}
            className={cn("flex flex-1 flex-col items-center gap-0.5 rounded-2xl py-2 text-[11px] font-medium", active(href) ? "bg-accent text-white" : "text-muted")}>
            <Icon className="h-5 w-5" />{label}
          </Link>
        ))}
      </nav>
    </div>
  );
}
