"use client";

import { useState, useEffect, useCallback } from "react";
import { motion } from "framer-motion";
import {
  Shield,
  Users,
  ShoppingCart,
  FileText,
  Package,
  LayoutDashboard,
  ScrollText,
  Loader2,
  Check,
  RotateCcw,
  ChevronDown,
} from "lucide-react";
import { Header } from "@/components/layout/header";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/lib/auth";
import type { AdminUser } from "@/lib/types";
import * as api from "@/lib/api";

const RESOURCES = [
  { key: "customers", label: "Customers", icon: Users },
  { key: "articles", label: "Articles", icon: Package },
  { key: "orders", label: "Orders", icon: ShoppingCart },
  { key: "invoices", label: "Invoices", icon: FileText },
  { key: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { key: "audit_log", label: "Audit Log", icon: ScrollText },
] as const;

const ACTIONS = ["read", "create", "update", "delete"] as const;

const ROLE_LABELS: Record<string, { label: string; color: string }> = {
  admin: { label: "Admin", color: "text-red-400 bg-red-500/10 border-red-500/20" },
  manager: { label: "Manager", color: "text-amber-400 bg-amber-500/10 border-amber-500/20" },
  member: { label: "Member", color: "text-blue-400 bg-blue-500/10 border-blue-500/20" },
  viewer: { label: "Viewer", color: "text-zinc-400 bg-zinc-500/10 border-zinc-500/20" },
};

type PermMap = Record<string, { read: boolean; create: boolean; update: boolean; delete: boolean }>;

interface UserPermState {
  userId: string;
  name: string;
  email: string;
  role: string;
  permissions: PermMap;
  dirty: boolean;
  saving: boolean;
}

export default function PermissionsPage() {
  const currentUser = useAuthStore((s) => s.user);
  const isAdmin = currentUser?.role === "admin";
  const isManager = currentUser?.role === "manager";
  const canManage = isAdmin || isManager;

  const [users, setUsers] = useState<AdminUser[]>([]);
  const [userPerms, setUserPerms] = useState<Record<string, UserPermState>>({});
  const [loading, setLoading] = useState(true);
  const [expandedUser, setExpandedUser] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const loadUsers = useCallback(async () => {
    try {
      const data = await api.getUsers();
      setUsers(data.users);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadUsers();
  }, [loadUsers]);

  const loadUserPerms = useCallback(async (userId: string) => {
    try {
      const data = await api.getUserErpPermissions(userId);
      const user = users.find((u) => u.id === userId);
      setUserPerms((prev) => ({
        ...prev,
        [userId]: {
          userId,
          name: data.name,
          email: user?.email ?? "",
          role: data.role,
          permissions: data.permissions,
          dirty: false,
          saving: false,
        },
      }));
    } catch {
      // ignore
    }
  }, [users]);

  const toggleUser = useCallback(
    (userId: string) => {
      if (expandedUser === userId) {
        setExpandedUser(null);
      } else {
        setExpandedUser(userId);
        if (!userPerms[userId]) {
          loadUserPerms(userId);
        }
      }
    },
    [expandedUser, userPerms, loadUserPerms]
  );

  const togglePerm = (userId: string, resource: string, action: string) => {
    setUserPerms((prev) => {
      const state = prev[userId];
      if (!state) return prev;
      const resourcePerms = { ...state.permissions[resource] };
      (resourcePerms as Record<string, boolean>)[action] = !(resourcePerms as Record<string, boolean>)[action];
      return {
        ...prev,
        [userId]: {
          ...state,
          permissions: { ...state.permissions, [resource]: resourcePerms },
          dirty: true,
        },
      };
    });
  };

  const savePerms = async (userId: string) => {
    const state = userPerms[userId];
    if (!state) return;

    setUserPerms((prev) => ({
      ...prev,
      [userId]: { ...prev[userId], saving: true },
    }));

    try {
      const permArray = Object.entries(state.permissions).map(([resource, perms]) => ({
        resource,
        can_read: perms.read,
        can_create: perms.create,
        can_update: perms.update,
        can_delete: perms.delete,
      }));
      await api.setUserErpPermissions(userId, permArray);
      setUserPerms((prev) => ({
        ...prev,
        [userId]: { ...prev[userId], dirty: false, saving: false },
      }));
      setSuccessMsg(`Permissions for ${state.name} saved.`);
      setTimeout(() => setSuccessMsg(null), 3000);
    } catch {
      setUserPerms((prev) => ({
        ...prev,
        [userId]: { ...prev[userId], saving: false },
      }));
    }
  };

  const resetPerms = async (userId: string) => {
    try {
      await api.resetUserErpPermissions(userId);
      await loadUserPerms(userId);
      const state = userPerms[userId];
      setSuccessMsg(`Permissions for ${state?.name ?? userId} reset to role defaults.`);
      setTimeout(() => setSuccessMsg(null), 3000);
    } catch {
      // ignore
    }
  };

  if (!canManage) {
    return (
      <div>
        <Header title="Permissions" subtitle="ERP access control" />
        <div className="px-8 py-12 text-center">
          <div className="flex justify-center mb-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-red-500/10">
              <Shield className="h-6 w-6 text-red-400" />
            </div>
          </div>
          <p className="text-muted-foreground">
            Only admins and managers can manage ERP permissions.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div>
      <Header title="Permissions" subtitle="Manage ERP access per user" />

      <motion.div
        className="px-8 py-6 space-y-4"
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, ease: "easeOut" }}
      >
        {successMsg && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 px-4 py-3 text-sm text-emerald-400 flex items-center gap-2"
          >
            <Check className="h-4 w-4" />
            {successMsg}
          </motion.div>
        )}

        <div className="rounded-xl border border-foreground/[0.06] bg-card/30 p-4">
          <p className="text-xs text-muted-foreground">
            <strong>Role defaults</strong> apply automatically. Per-user overrides take
            precedence. Admin = full access, Manager = CRUD (no delete on orders/invoices),
            Member = read + create, Viewer = read-only.
          </p>
        </div>

        {loading ? (
          <div className="space-y-2">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="rounded-xl border border-foreground/[0.06] bg-card/50 p-4 h-16 animate-shimmer bg-[length:200%_100%] bg-gradient-to-r from-foreground/[0.03] via-foreground/[0.06] to-foreground/[0.03]"
              />
            ))}
          </div>
        ) : users.length === 0 ? (
          <div className="rounded-xl border border-dashed border-foreground/[0.1] bg-card/30 p-12 text-center">
            <p className="text-muted-foreground">No users found.</p>
          </div>
        ) : (
          <div className="space-y-2">
            {users.map((u) => {
              const isExpanded = expandedUser === u.id;
              const state = userPerms[u.id];
              const roleInfo = ROLE_LABELS[u.role] ?? ROLE_LABELS.member;

              return (
                <div
                  key={u.id}
                  className="rounded-xl border border-foreground/[0.06] bg-card/80 backdrop-blur-sm overflow-hidden transition-all duration-200"
                >
                  {/* User row */}
                  <button
                    onClick={() => toggleUser(u.id)}
                    className="w-full flex items-center justify-between px-4 py-3 hover:bg-foreground/[0.02] transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 text-primary text-xs font-bold">
                        {u.name.charAt(0).toUpperCase()}
                      </div>
                      <div className="text-left">
                        <p className="text-sm font-medium">{u.name}</p>
                        <p className="text-xs text-muted-foreground">{u.email}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <span
                        className={cn(
                          "inline-flex items-center rounded-full border px-2.5 py-0.5 text-[10px] font-medium capitalize",
                          roleInfo.color
                        )}
                      >
                        {roleInfo.label}
                      </span>
                      {state?.dirty && (
                        <span className="h-2 w-2 rounded-full bg-amber-400" />
                      )}
                      <ChevronDown
                        className={cn(
                          "h-4 w-4 text-muted-foreground transition-transform duration-200",
                          isExpanded && "rotate-180"
                        )}
                      />
                    </div>
                  </button>

                  {/* Permissions grid */}
                  {isExpanded && (
                    <motion.div
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: "auto" }}
                      className="border-t border-foreground/[0.06] px-4 py-4"
                    >
                      {!state ? (
                        <div className="flex items-center justify-center py-4">
                          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                        </div>
                      ) : (
                        <>
                          <div className="overflow-x-auto">
                            <table className="w-full text-sm">
                              <thead>
                                <tr className="border-b border-foreground/[0.06]">
                                  <th className="text-left px-3 py-2 text-xs font-medium text-muted-foreground w-40">
                                    Resource
                                  </th>
                                  {ACTIONS.map((action) => (
                                    <th
                                      key={action}
                                      className="text-center px-3 py-2 text-xs font-medium text-muted-foreground capitalize w-24"
                                    >
                                      {action}
                                    </th>
                                  ))}
                                </tr>
                              </thead>
                              <tbody>
                                {RESOURCES.map((res) => {
                                  const Icon = res.icon;
                                  const perms = state.permissions[res.key];
                                  return (
                                    <tr
                                      key={res.key}
                                      className="border-b border-foreground/[0.04] last:border-0"
                                    >
                                      <td className="px-3 py-2.5">
                                        <span className="flex items-center gap-2 text-sm">
                                          <Icon className="h-3.5 w-3.5 text-muted-foreground" />
                                          {res.label}
                                        </span>
                                      </td>
                                      {ACTIONS.map((action) => {
                                        const checked = perms?.[action] ?? false;
                                        return (
                                          <td key={action} className="text-center px-3 py-2.5">
                                            <button
                                              onClick={() => togglePerm(u.id, res.key, action)}
                                              className={cn(
                                                "h-5 w-5 rounded border transition-all duration-150 inline-flex items-center justify-center",
                                                checked
                                                  ? "bg-primary border-primary text-primary-foreground"
                                                  : "border-foreground/20 bg-foreground/[0.03] hover:border-foreground/40"
                                              )}
                                            >
                                              {checked && <Check className="h-3 w-3" />}
                                            </button>
                                          </td>
                                        );
                                      })}
                                    </tr>
                                  );
                                })}
                              </tbody>
                            </table>
                          </div>

                          {/* Actions */}
                          <div className="flex items-center justify-between pt-4 mt-4 border-t border-foreground/[0.06]">
                            <button
                              onClick={() => resetPerms(u.id)}
                              className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs text-muted-foreground hover:text-foreground hover:bg-foreground/[0.04] transition-colors"
                            >
                              <RotateCcw className="h-3.5 w-3.5" />
                              Reset to role defaults
                            </button>
                            <button
                              onClick={() => savePerms(u.id)}
                              disabled={!state.dirty || state.saving}
                              className={cn(
                                "flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-medium transition-all",
                                state.dirty
                                  ? "bg-primary text-primary-foreground shadow-lg shadow-primary/20 hover:bg-primary/90"
                                  : "bg-foreground/[0.06] text-muted-foreground cursor-not-allowed"
                              )}
                            >
                              {state.saving ? (
                                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                              ) : (
                                <Check className="h-3.5 w-3.5" />
                              )}
                              Save permissions
                            </button>
                          </div>
                        </>
                      )}
                    </motion.div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </motion.div>
    </div>
  );
}
