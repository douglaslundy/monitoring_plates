"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import {
  LayoutDashboard,
  Building2,
  CreditCard,
  Users,
  Camera,
  Radio,
  Search,
  Bell,
  BellRing,
  MessageCircle,
  Settings,
  LogOut,
  Menu,
  X,
  Shield,
  ScanLine,
  ScanSearch,
  Activity,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { logout } from "@/lib/auth";
import type { LucideIcon } from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  exact?: boolean;
  badge?: number;
}

const ADMIN_NAV: NavItem[] = [
  { href: "/admin", label: "Dashboard", icon: LayoutDashboard, exact: true },
  { href: "/admin/clients", label: "Clientes", icon: Building2 },
  { href: "/admin/plans", label: "Planos", icon: CreditCard },
  { href: "/admin/users", label: "Usuarios", icon: Users },
  { href: "/admin/cameras", label: "Cameras", icon: Camera },
  { href: "/admin/live", label: "Live", icon: Radio },
  { href: "/admin/metricas", label: "Metricas", icon: Activity },
  { href: "/admin/search", label: "Placas", icon: Search },
  { href: "/admin/alerts", label: "Alertas cadastrados", icon: Bell },
  { href: "/admin/alertas-disparados", label: "Alertas disparados", icon: BellRing },
  { href: "/admin/detections", label: "Deteccoes", icon: ScanSearch },
  { href: "/admin/ocr-config", label: "Motores OCR", icon: ScanLine },
  { href: "/admin/whatsapp", label: "WhatsApp", icon: MessageCircle },
];

export const CLIENT_NAV: NavItem[] = [
  { href: "/client", label: "Dashboard", icon: LayoutDashboard, exact: true },
  { href: "/client/search", label: "Placas", icon: Search },
  { href: "/client/detections", label: "Deteccoes", icon: ScanSearch },
  { href: "/client/alerts", label: "Alertas", icon: Bell },
  { href: "/client/cameras", label: "Cameras", icon: Camera },
  { href: "/client/live", label: "Live", icon: Radio },
  { href: "/client/settings", label: "Configuracoes", icon: Settings },
];

function Logo() {
  return (
    <div className="relative h-8 w-8 shrink-0" aria-hidden="true">
      <Shield className="h-8 w-8 text-primary" />
      <Camera className="absolute inset-0 m-auto h-4 w-4 text-primary-foreground" />
    </div>
  );
}

interface SidebarProps {
  userName?: string;
  userEmail?: string;
  navItems?: NavItem[];
  appName?: string;
}

export function Sidebar({
  userName,
  userEmail,
  navItems = ADMIN_NAV,
  appName = "Monitoramento",
}: SidebarProps) {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);

  const isActive = (href: string, exact?: boolean) =>
    exact ? pathname === href : pathname.startsWith(href);

  const navContent = (
    <div className="flex flex-col h-full">
      <div className="p-5 border-b flex items-center gap-3">
        <Logo />
        <div>
          <h1 className="font-bold text-sm text-primary leading-tight">{appName}</h1>
          <p className="text-xs text-muted-foreground">Sistema de Transito</p>
        </div>
      </div>

      <nav role="navigation" aria-label="Menu principal" className="flex-1 min-h-0 p-3 space-y-0.5">
        {navItems.map((item) => {
          const Icon = item.icon;
          const active = isActive(item.href, item.exact);
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={() => setMobileOpen(false)}
              aria-current={active ? "page" : undefined}
              className={cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-primary/50",
                active ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-accent hover:text-foreground"
              )}
            >
              <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
              <span className="flex-1">{item.label}</span>
              {item.badge != null && item.badge > 0 && (
                <span
                  aria-label={`${item.badge} nao lidos`}
                  className={cn(
                    "inline-flex items-center justify-center h-4 min-w-4 px-1 rounded-full text-xs font-bold",
                    active ? "bg-primary-foreground/20 text-primary-foreground" : "bg-red-500 text-white"
                  )}
                >
                  {item.badge > 99 ? "99+" : item.badge}
                </span>
              )}
            </Link>
          );
        })}
      </nav>

      <div className="p-3 border-t">
        <div className="flex items-center gap-3 px-3 py-2 mb-0.5">
          <div className="h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center shrink-0" aria-hidden="true">
            <span className="text-xs font-bold text-primary">{userName?.charAt(0).toUpperCase() ?? "U"}</span>
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium truncate">{userName ?? "Usuario"}</p>
            <p className="text-xs text-muted-foreground truncate">{userEmail ?? ""}</p>
          </div>
        </div>
        <button
          onClick={logout}
          aria-label="Sair do sistema"
          className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-muted-foreground hover:bg-destructive/10 hover:text-destructive transition-colors w-full focus:outline-none focus:ring-2 focus:ring-destructive/50"
        >
          <LogOut className="h-4 w-4 shrink-0" aria-hidden="true" />
          Sair
        </button>
      </div>
    </div>
  );

  return (
    <>
      <div className="lg:hidden fixed top-0 left-0 right-0 z-20 bg-white border-b px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Logo />
          <span className="font-bold text-primary text-sm">{appName}</span>
        </div>
        <button
          onClick={() => setMobileOpen(!mobileOpen)}
          className="p-2 -mr-2 rounded-lg hover:bg-gray-100 transition-colors focus:outline-none focus:ring-2 focus:ring-primary/50"
          aria-label={mobileOpen ? "Fechar menu" : "Abrir menu"}
          aria-expanded={mobileOpen}
        >
          {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </div>

      {mobileOpen && <div className="lg:hidden fixed inset-0 z-30 bg-black/40" onClick={() => setMobileOpen(false)} aria-hidden="true" />}

      <div
        className={cn(
          "lg:hidden fixed inset-y-0 left-0 z-40 w-64 bg-white border-r shadow-lg transition-transform duration-200",
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        )}
        aria-hidden={!mobileOpen}
      >
        {navContent}
      </div>

      <aside className="hidden lg:flex lg:flex-col lg:fixed lg:inset-y-0 lg:w-64 bg-white border-r">{navContent}</aside>
    </>
  );
}

export { ADMIN_NAV };
