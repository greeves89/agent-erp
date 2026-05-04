"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { Users, ShoppingCart, FileText, DollarSign } from "lucide-react";
import { Header } from "@/components/layout/header";
import { cn } from "@/lib/utils";
import * as api from "@/lib/api";

const statConfig = [
  {
    key: "customers",
    label: "Customers",
    icon: Users,
    color: "text-blue-400",
    gradient: "from-blue-500/20 via-blue-500/5 to-transparent",
    iconBg: "bg-blue-500/10",
    format: (v: number) => String(v),
  },
  {
    key: "open_orders",
    label: "Open Orders",
    icon: ShoppingCart,
    color: "text-amber-400",
    gradient: "from-amber-500/20 via-amber-500/5 to-transparent",
    iconBg: "bg-amber-500/10",
    format: (v: number) => String(v),
  },
  {
    key: "overdue_invoices",
    label: "Overdue Invoices",
    icon: FileText,
    color: "text-red-400",
    gradient: "from-red-500/20 via-red-500/5 to-transparent",
    iconBg: "bg-red-500/10",
    format: (v: number) => String(v),
  },
  {
    key: "monthly_revenue",
    label: "Monthly Revenue",
    icon: DollarSign,
    color: "text-emerald-400",
    gradient: "from-emerald-500/20 via-emerald-500/5 to-transparent",
    iconBg: "bg-emerald-500/10",
    format: (v: number) =>
      new Intl.NumberFormat("de-DE", { style: "currency", currency: "EUR" }).format(v),
  },
];

export default function ErpOverviewPage() {
  const [data, setData] = useState<api.ErpDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const d = await api.getErpDashboard();
        if (!cancelled) setData(d);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    const interval = setInterval(load, 30000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  const values: Record<string, number> = {
    customers: data?.customer_count ?? 0,
    open_orders: data?.open_orders ?? 0,
    overdue_invoices: data?.overdue_invoices ?? 0,
    monthly_revenue: data?.monthly_revenue ?? 0,
  };

  return (
    <div>
      <Header title="ERP" subtitle="Enterprise Resource Planning overview" />

      <motion.div
        className="px-8 py-8 space-y-8"
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, ease: "easeOut" }}
      >
        {error ? (
          <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-6 text-center text-sm text-red-400">
            {error}
          </div>
        ) : loading ? (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {[1, 2, 3, 4].map((i) => (
              <div
                key={i}
                className="rounded-xl border border-foreground/[0.06] bg-card/50 p-4 h-[110px] animate-shimmer bg-[length:200%_100%] bg-gradient-to-r from-foreground/[0.03] via-foreground/[0.06] to-foreground/[0.03]"
              />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {statConfig.map((stat) => {
              const Icon = stat.icon;
              return (
                <div
                  key={stat.key}
                  className="relative overflow-hidden rounded-xl border border-foreground/[0.06] bg-card/80 backdrop-blur-sm p-4 transition-all duration-200 hover:border-foreground/[0.1]"
                >
                  <div
                    className={cn(
                      "absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent to-transparent",
                      stat.gradient
                    )}
                  />
                  <div className="flex items-center justify-between mb-2">
                    <div className={cn("flex h-8 w-8 items-center justify-center rounded-lg", stat.iconBg)}>
                      <Icon className={cn("h-4 w-4", stat.color)} />
                    </div>
                  </div>
                  <p className="text-[11px] font-medium text-muted-foreground mb-0.5">
                    {stat.label}
                  </p>
                  <p className={cn("text-2xl font-bold tabular-nums leading-none tracking-tight", stat.color)}>
                    {stat.format(values[stat.key])}
                  </p>
                </div>
              );
            })}
          </div>
        )}
      </motion.div>
    </div>
  );
}
