"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { useErpPermissions } from "@/hooks/use-erp-permissions";
import {
  LayoutDashboard,
  Users,
  ShoppingCart,
  FileText,
  Lock,
} from "lucide-react";

const erpNav = [
  { href: "/erp", label: "Overview", icon: LayoutDashboard, exact: true, resource: "dashboard" },
  { href: "/erp/customers", label: "Customers", icon: Users, exact: false, resource: "customers" },
  { href: "/erp/orders", label: "Orders", icon: ShoppingCart, exact: false, resource: "orders" },
  { href: "/erp/invoices", label: "Invoices", icon: FileText, exact: false, resource: "invoices" },
];

export default function ErpLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { can, loading } = useErpPermissions();

  const visibleNav = erpNav.filter((item) => can(item.resource, "read"));

  return (
    <div>
      <div className="border-b border-foreground/[0.06] bg-background/60 backdrop-blur-sm px-8">
        <div className="flex items-center gap-1 py-2">
          {loading
            ? erpNav.map((item) => (
                <div
                  key={item.href}
                  className="rounded-lg px-3 py-2 h-8 w-24 animate-pulse bg-foreground/[0.04]"
                />
              ))
            : visibleNav.map((item) => {
                const Icon = item.icon;
                const isActive = item.exact
                  ? pathname === item.href
                  : pathname.startsWith(item.href);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={cn(
                      "flex items-center gap-2 rounded-lg px-3 py-2 text-[13px] font-medium transition-all duration-150",
                      isActive
                        ? "bg-foreground/[0.08] text-foreground shadow-sm"
                        : "text-muted-foreground hover:text-foreground hover:bg-foreground/[0.04]"
                    )}
                  >
                    <Icon className={cn("h-4 w-4", isActive ? "text-primary" : "")} />
                    {item.label}
                  </Link>
                );
              })}
        </div>
      </div>

      {children}
    </div>
  );
}
