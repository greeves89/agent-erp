"use client";

import { useState, useEffect, useCallback } from "react";
import { motion } from "framer-motion";
import {
  Plus,
  Search,
  Users,
  Loader2,
  X,
  CheckCircle2,
  XCircle,
} from "lucide-react";
import { Header } from "@/components/layout/header";
import { cn } from "@/lib/utils";
import { useErpPermissions } from "@/hooks/use-erp-permissions";
import * as api from "@/lib/api";

export default function CustomersPage() {
  const { can } = useErpPermissions();
  const [customers, setCustomers] = useState<api.ErpCustomer[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);

  // Create form
  const [formCompany, setFormCompany] = useState("");
  const [formContact, setFormContact] = useState("");
  const [formEmail, setFormEmail] = useState("");
  const [formPhone, setFormPhone] = useState("");
  const [formAddress, setFormAddress] = useState("");

  const refresh = useCallback(async () => {
    try {
      const data = await api.getErpCustomers(search || undefined);
      setCustomers(data.customers);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, [search]);

  useEffect(() => {
    setLoading(true);
    const timer = setTimeout(() => refresh(), search ? 300 : 0);
    return () => clearTimeout(timer);
  }, [refresh, search]);

  useEffect(() => {
    const interval = setInterval(refresh, 30000);
    return () => clearInterval(interval);
  }, [refresh]);

  const handleCreate = async () => {
    if (!formCompany.trim()) return;
    setCreating(true);
    try {
      await api.createErpCustomer({
        company_name: formCompany.trim(),
        contact_name: formContact.trim() || undefined,
        email: formEmail.trim() || undefined,
        phone: formPhone.trim() || undefined,
        address: formAddress.trim() || undefined,
      });
      setFormCompany("");
      setFormContact("");
      setFormEmail("");
      setFormPhone("");
      setFormAddress("");
      setShowCreate(false);
      await refresh();
    } catch {
      // ignore
    } finally {
      setCreating(false);
    }
  };

  return (
    <div>
      <Header
        title="Customers"
        subtitle="Manage your customer database"
        actions={
          can("customers", "create") ? (
            <button
              onClick={() => setShowCreate(!showCreate)}
              className="inline-flex items-center gap-2 rounded-xl bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground shadow-lg shadow-primary/20 hover:bg-primary/90 transition-all duration-200 hover:shadow-primary/30 hover:-translate-y-0.5"
            >
              <Plus className="h-4 w-4" />
              New Customer
            </button>
          ) : undefined
        }
      />

      <div className="px-8 py-6 space-y-6">
        {/* Create Form */}
        {showCreate && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="overflow-hidden rounded-2xl border border-foreground/[0.06] bg-card/80 p-6 backdrop-blur-sm"
          >
            <div className="mb-4 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Users className="h-4 w-4 text-primary" />
                <h3 className="text-sm font-semibold">New Customer</h3>
              </div>
              <button
                onClick={() => setShowCreate(false)}
                className="text-muted-foreground hover:text-foreground transition-colors"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
                  Company Name *
                </label>
                <input
                  value={formCompany}
                  onChange={(e) => setFormCompany(e.target.value)}
                  placeholder="Acme Corp"
                  className="w-full rounded-xl border border-foreground/[0.06] bg-foreground/[0.03] px-4 py-2.5 text-sm placeholder:text-muted-foreground/40 focus:border-primary/50 focus:outline-none focus:ring-1 focus:ring-primary/25"
                />
              </div>
              <div>
                <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
                  Contact Name
                </label>
                <input
                  value={formContact}
                  onChange={(e) => setFormContact(e.target.value)}
                  placeholder="John Doe"
                  className="w-full rounded-xl border border-foreground/[0.06] bg-foreground/[0.03] px-4 py-2.5 text-sm placeholder:text-muted-foreground/40 focus:border-primary/50 focus:outline-none focus:ring-1 focus:ring-primary/25"
                />
              </div>
              <div>
                <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
                  Email
                </label>
                <input
                  value={formEmail}
                  onChange={(e) => setFormEmail(e.target.value)}
                  placeholder="info@acme.com"
                  type="email"
                  className="w-full rounded-xl border border-foreground/[0.06] bg-foreground/[0.03] px-4 py-2.5 text-sm placeholder:text-muted-foreground/40 focus:border-primary/50 focus:outline-none focus:ring-1 focus:ring-primary/25"
                />
              </div>
              <div>
                <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
                  Phone
                </label>
                <input
                  value={formPhone}
                  onChange={(e) => setFormPhone(e.target.value)}
                  placeholder="+49 123 456789"
                  className="w-full rounded-xl border border-foreground/[0.06] bg-foreground/[0.03] px-4 py-2.5 text-sm placeholder:text-muted-foreground/40 focus:border-primary/50 focus:outline-none focus:ring-1 focus:ring-primary/25"
                />
              </div>
              <div className="md:col-span-2">
                <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
                  Address
                </label>
                <input
                  value={formAddress}
                  onChange={(e) => setFormAddress(e.target.value)}
                  placeholder="123 Main St, Berlin"
                  className="w-full rounded-xl border border-foreground/[0.06] bg-foreground/[0.03] px-4 py-2.5 text-sm placeholder:text-muted-foreground/40 focus:border-primary/50 focus:outline-none focus:ring-1 focus:ring-primary/25"
                />
              </div>
            </div>
            <div className="flex justify-end gap-3 pt-4">
              <button
                onClick={() => setShowCreate(false)}
                className="rounded-xl px-4 py-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleCreate}
                disabled={!formCompany.trim() || creating}
                className="flex items-center gap-2 rounded-xl bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground transition-all hover:brightness-110 disabled:opacity-50"
              >
                {creating && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                Create Customer
              </button>
            </div>
          </motion.div>
        )}

        {/* Search */}
        <div className="relative w-full max-w-md">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground/50" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search customers..."
            className="w-full rounded-xl border border-foreground/[0.06] bg-foreground/[0.03] pl-10 pr-4 py-2.5 text-sm placeholder:text-muted-foreground/40 focus:border-primary/50 focus:outline-none focus:ring-1 focus:ring-primary/25"
          />
        </div>

        {/* Table */}
        {error ? (
          <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-6 text-center text-sm text-red-400">
            {error}
          </div>
        ) : loading && customers.length === 0 ? (
          <div className="space-y-2">
            {[1, 2, 3, 4, 5].map((i) => (
              <div
                key={i}
                className="rounded-xl border border-foreground/[0.06] bg-card/50 p-4 h-16 animate-shimmer bg-[length:200%_100%] bg-gradient-to-r from-foreground/[0.03] via-foreground/[0.06] to-foreground/[0.03]"
              />
            ))}
          </div>
        ) : customers.length === 0 ? (
          <div className="rounded-xl border border-dashed border-foreground/[0.1] bg-card/30 p-12 text-center">
            <div className="flex justify-center mb-4">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10">
                <Users className="h-6 w-6 text-primary" />
              </div>
            </div>
            <p className="text-muted-foreground mb-2">No customers found</p>
            <p className="text-xs text-muted-foreground/60">
              {search ? "Try a different search term" : "Create your first customer to get started"}
            </p>
          </div>
        ) : (
          <div className="rounded-xl border border-foreground/[0.06] overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-foreground/[0.06] bg-foreground/[0.02]">
                  <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground">
                    Customer No.
                  </th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground">
                    Company
                  </th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground hidden md:table-cell">
                    Email
                  </th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground hidden lg:table-cell">
                    Phone
                  </th>
                  <th className="text-center px-4 py-3 text-xs font-medium text-muted-foreground">
                    Status
                  </th>
                </tr>
              </thead>
              <tbody>
                {customers.map((customer, i) => (
                  <motion.tr
                    key={customer.id}
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.02, duration: 0.2 }}
                    className="border-b border-foreground/[0.04] hover:bg-foreground/[0.02] cursor-pointer transition-colors"
                  >
                    <td className="px-4 py-3 font-mono text-xs text-muted-foreground">
                      {customer.customer_number}
                    </td>
                    <td className="px-4 py-3 font-medium">
                      {customer.company_name}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground hidden md:table-cell">
                      {customer.email || "---"}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground hidden lg:table-cell">
                      {customer.phone || "---"}
                    </td>
                    <td className="px-4 py-3 text-center">
                      {customer.is_active ? (
                        <span className="inline-flex items-center gap-1 rounded-full border border-emerald-500/20 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-medium text-emerald-400">
                          <CheckCircle2 className="h-3 w-3" />
                          Active
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 rounded-full border border-zinc-500/20 bg-zinc-500/10 px-2 py-0.5 text-[10px] font-medium text-zinc-400">
                          <XCircle className="h-3 w-3" />
                          Inactive
                        </span>
                      )}
                    </td>
                  </motion.tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
