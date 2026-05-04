"use client";

import { useState, useEffect, useCallback } from "react";
import { motion } from "framer-motion";
import { ShoppingCart, Calendar, Hash } from "lucide-react";
import { Header } from "@/components/layout/header";
import { cn } from "@/lib/utils";
import * as api from "@/lib/api";

const statusBadge: Record<string, { bg: string; text: string }> = {
  draft: { bg: "bg-zinc-500/10 border-zinc-500/20", text: "text-zinc-400" },
  confirmed: { bg: "bg-blue-500/10 border-blue-500/20", text: "text-blue-400" },
  shipped: { bg: "bg-amber-500/10 border-amber-500/20", text: "text-amber-400" },
  delivered: { bg: "bg-emerald-500/10 border-emerald-500/20", text: "text-emerald-400" },
  cancelled: { bg: "bg-red-500/10 border-red-500/20", text: "text-red-400" },
};

const typeBadge: Record<string, { bg: string; text: string; label: string }> = {
  sale: { bg: "bg-blue-500/10 border-blue-500/20", text: "text-blue-400", label: "Sale" },
  purchase: { bg: "bg-violet-500/10 border-violet-500/20", text: "text-violet-400", label: "Purchase" },
};

const statusFilters = ["all", "draft", "confirmed", "shipped", "delivered", "cancelled"];
const typeFilters = ["all", "sale", "purchase"];

export default function OrdersPage() {
  const [orders, setOrders] = useState<api.ErpOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState("all");
  const [typeFilter, setTypeFilter] = useState("all");

  const refresh = useCallback(async () => {
    try {
      const data = await api.getErpOrders({
        status: statusFilter !== "all" ? statusFilter : undefined,
        type: typeFilter !== "all" ? typeFilter : undefined,
      });
      setOrders(data.orders);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, [statusFilter, typeFilter]);

  useEffect(() => {
    setLoading(true);
    refresh();
  }, [refresh]);

  useEffect(() => {
    const interval = setInterval(refresh, 30000);
    return () => clearInterval(interval);
  }, [refresh]);

  const formatCurrency = (amount: number, currency: string) =>
    new Intl.NumberFormat("de-DE", { style: "currency", currency }).format(amount);

  return (
    <div>
      <Header title="Orders" subtitle="Manage purchase and sales orders" />

      <div className="px-8 py-6 space-y-6">
        {/* Filters */}
        <div className="flex flex-wrap items-center gap-4">
          {/* Status filter */}
          <div className="flex gap-1 p-1 rounded-xl bg-foreground/[0.03] border border-foreground/[0.06] w-fit">
            {statusFilters.map((s) => (
              <button
                key={s}
                onClick={() => setStatusFilter(s)}
                className={cn(
                  "rounded-lg px-3 py-1.5 text-xs font-medium transition-all duration-150 capitalize",
                  statusFilter === s
                    ? "bg-foreground/[0.08] text-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground hover:bg-foreground/[0.04]"
                )}
              >
                {s === "all" ? "All Status" : s}
              </button>
            ))}
          </div>

          {/* Type filter */}
          <div className="flex gap-1 p-1 rounded-xl bg-foreground/[0.03] border border-foreground/[0.06] w-fit">
            {typeFilters.map((t) => (
              <button
                key={t}
                onClick={() => setTypeFilter(t)}
                className={cn(
                  "rounded-lg px-3 py-1.5 text-xs font-medium transition-all duration-150 capitalize",
                  typeFilter === t
                    ? "bg-foreground/[0.08] text-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground hover:bg-foreground/[0.04]"
                )}
              >
                {t === "all" ? "All Types" : t}
              </button>
            ))}
          </div>
        </div>

        {/* Table */}
        {error ? (
          <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-6 text-center text-sm text-red-400">
            {error}
          </div>
        ) : loading && orders.length === 0 ? (
          <div className="space-y-2">
            {[1, 2, 3, 4, 5].map((i) => (
              <div
                key={i}
                className="rounded-xl border border-foreground/[0.06] bg-card/50 p-4 h-16 animate-shimmer bg-[length:200%_100%] bg-gradient-to-r from-foreground/[0.03] via-foreground/[0.06] to-foreground/[0.03]"
              />
            ))}
          </div>
        ) : orders.length === 0 ? (
          <div className="rounded-xl border border-dashed border-foreground/[0.1] bg-card/30 p-12 text-center">
            <div className="flex justify-center mb-4">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10">
                <ShoppingCart className="h-6 w-6 text-primary" />
              </div>
            </div>
            <p className="text-muted-foreground mb-2">No orders found</p>
            <p className="text-xs text-muted-foreground/60">
              {statusFilter !== "all" || typeFilter !== "all"
                ? "Try adjusting your filters"
                : "No orders have been created yet"}
            </p>
          </div>
        ) : (
          <div className="rounded-xl border border-foreground/[0.06] overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-foreground/[0.06] bg-foreground/[0.02]">
                  <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground">
                    Order No.
                  </th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground">
                    Type
                  </th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground">
                    Customer / Supplier
                  </th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground">
                    Status
                  </th>
                  <th className="text-right px-4 py-3 text-xs font-medium text-muted-foreground">
                    Total
                  </th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground hidden md:table-cell">
                    Date
                  </th>
                </tr>
              </thead>
              <tbody>
                {orders.map((order, i) => {
                  const sBadge = statusBadge[order.status] ?? statusBadge.draft;
                  const tBadge = typeBadge[order.type] ?? typeBadge.sale;
                  return (
                    <motion.tr
                      key={order.id}
                      initial={{ opacity: 0, y: 4 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: i * 0.02, duration: 0.2 }}
                      className="border-b border-foreground/[0.04] hover:bg-foreground/[0.02] cursor-pointer transition-colors"
                    >
                      <td className="px-4 py-3">
                        <span className="flex items-center gap-1.5 font-mono text-xs text-muted-foreground">
                          <Hash className="h-3 w-3" />
                          {order.order_number}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={cn(
                            "inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-medium",
                            tBadge.bg,
                            tBadge.text
                          )}
                        >
                          {tBadge.label}
                        </span>
                      </td>
                      <td className="px-4 py-3 font-medium">
                        {order.customer_name || order.supplier_name || "---"}
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={cn(
                            "inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-medium capitalize",
                            sBadge.bg,
                            sBadge.text
                          )}
                        >
                          {order.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right font-mono text-sm tabular-nums">
                        {formatCurrency(order.total, order.currency)}
                      </td>
                      <td className="px-4 py-3 hidden md:table-cell">
                        <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                          <Calendar className="h-3 w-3" />
                          {new Date(order.order_date).toLocaleDateString()}
                        </span>
                      </td>
                    </motion.tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
