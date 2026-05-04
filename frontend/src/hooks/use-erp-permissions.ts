"use client";

import { useState, useEffect, useCallback } from "react";
import * as api from "@/lib/api";

const DEFAULT_PERMS: api.ErpPermissions = {
  customers: { read: false, create: false, update: false, delete: false },
  articles: { read: false, create: false, update: false, delete: false },
  orders: { read: false, create: false, update: false, delete: false },
  invoices: { read: false, create: false, update: false, delete: false },
  dashboard: { read: false, create: false, update: false, delete: false },
  audit_log: { read: false, create: false, update: false, delete: false },
};

export function useErpPermissions() {
  const [permissions, setPermissions] = useState<api.ErpPermissions>(DEFAULT_PERMS);
  const [role, setRole] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const data = await api.getMyErpPermissions();
      setPermissions(data.permissions);
      setRole(data.role);
    } catch {
      // Fallback: if permissions endpoint fails, assume full access (setup mode)
      setPermissions({
        customers: { read: true, create: true, update: true, delete: true },
        articles: { read: true, create: true, update: true, delete: true },
        orders: { read: true, create: true, update: true, delete: true },
        invoices: { read: true, create: true, update: true, delete: true },
        dashboard: { read: true, create: true, update: true, delete: true },
        audit_log: { read: true, create: true, update: true, delete: true },
      });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const can = useCallback(
    (resource: string, action: "read" | "create" | "update" | "delete") => {
      return permissions[resource]?.[action] ?? false;
    },
    [permissions]
  );

  return { permissions, role, loading, can, refresh };
}
