"use client";
import * as React from "react";
import * as SwitchPrimitive from "@radix-ui/react-switch";
import { Search } from "lucide-react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

/* Two radii on purpose: 22px for surfaces, 12px for controls. */
export const Card = ({ className, ...p }: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn("glass rounded-[22px]", className)} {...p} />
);

const button = cva(
  "inline-flex items-center justify-center gap-2 rounded-xl text-sm font-medium transition active:scale-[.97] disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        primary: "bg-accent text-white hover:brightness-110",
        glass: "glass-ctl hover:bg-white/80 dark:hover:bg-white/20",
        danger: "bg-danger/15 text-danger hover:bg-danger/25",
      },
      size: { sm: "h-8 px-3", md: "h-10 px-4", icon: "h-9 w-9" },
    },
    defaultVariants: { variant: "glass", size: "md" },
  }
);
export function Button({ className, variant, size, ...p }: React.ButtonHTMLAttributes<HTMLButtonElement> & VariantProps<typeof button>) {
  return <button className={cn(button({ variant, size }), className)} {...p} />;
}

const tones = {
  ok: "bg-ok/15 text-ok", warn: "bg-warn/15 text-warn", danger: "bg-danger/15 text-danger",
  accent: "bg-accent/15 text-accent", muted: "bg-fg/10 text-muted",
};
export const Badge = ({ tone = "muted", children }: { tone?: keyof typeof tones; children: React.ReactNode }) => (
  <span className={cn("inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium", tones[tone])}>{children}</span>
);

export function Toggle({ checked, onCheckedChange, label }: { checked: boolean; onCheckedChange: (v: boolean) => void; label: string }) {
  return (
    <SwitchPrimitive.Root
      checked={checked} onCheckedChange={onCheckedChange} aria-label={label}
      className="relative h-[26px] w-[44px] shrink-0 rounded-full bg-fg/20 transition-colors data-[state=checked]:bg-ok"
    >
      <SwitchPrimitive.Thumb className="block h-[22px] w-[22px] translate-x-[2px] rounded-full bg-white shadow-md transition-transform data-[state=checked]:translate-x-[20px]" />
    </SwitchPrimitive.Root>
  );
}

export function SearchField({ value, onChange, placeholder }: { value: string; onChange: (v: string) => void; placeholder: string }) {
  return (
    <label className="glass-ctl flex h-10 items-center gap-2 rounded-xl px-3 text-sm sm:w-64">
      <Search className="h-4 w-4 text-muted" />
      <input value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder}
        className="w-full bg-transparent outline-none placeholder:text-muted" />
    </label>
  );
}

export function Segmented<T extends string>({ value, onChange, options }: { value: T; onChange: (v: T) => void; options: { id: T; label: string; count?: number }[] }) {
  return (
    <div role="tablist" className="glass-ctl inline-flex rounded-xl p-1">
      {options.map((o) => (
        <button key={o.id} role="tab" aria-selected={value === o.id} onClick={() => onChange(o.id)}
          className={cn("h-8 rounded-[9px] px-4 text-sm font-medium transition",
            value === o.id ? "bg-white text-black shadow dark:bg-white/20 dark:text-white" : "text-muted hover:text-fg")}>
          {o.label}{o.count !== undefined && <span className="ml-1.5 text-muted">{o.count}</span>}
        </button>
      ))}
    </div>
  );
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: React.ReactNode }) {
  return (
    <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">{title}</h1>
        {subtitle && <p className="mt-1 text-muted">{subtitle}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}

export function Status({ loading, error, empty, children }: { loading: boolean; error: string | null; empty?: string; children: React.ReactNode }) {
  if (loading) return <div className="space-y-3 p-8 motion-safe:animate-pulse">{[0, 1, 2].map((i) => <div key={i} className="h-4 rounded bg-fg/10" />)}</div>;
  if (error) return (
    <div className="p-8 text-sm">
      <p className="font-medium text-danger">Can’t reach the router</p>
      <p className="mt-1 text-muted">{error}. Check ROS_HOST, ROS_USER and ROS_PASS in .env.local.</p>
    </div>
  );
  if (empty) return <div className="p-8 text-sm text-muted">{empty}</div>;
  return <>{children}</>;
}

export function DataTable({ head, children }: { head: string[]; children: React.ReactNode }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead><tr className="text-left text-muted">{head.map((h) => <th key={h} className="whitespace-nowrap px-5 py-3 font-medium">{h}</th>)}</tr></thead>
        <tbody className="divide-y divide-black/5 dark:divide-white/10">{children}</tbody>
      </table>
    </div>
  );
}
export const Tr = ({ className, ...p }: React.HTMLAttributes<HTMLTableRowElement>) => (
  <tr className={cn("transition-colors hover:bg-white/30 dark:hover:bg-white/[.04]", className)} {...p} />
);
export const Td = ({ className, ...p }: React.TdHTMLAttributes<HTMLTableCellElement>) => (
  <td className={cn("whitespace-nowrap px-5 py-3", className)} {...p} />
);
