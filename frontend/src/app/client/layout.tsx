"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { Sidebar, CLIENT_NAV } from "@/components/ui/Sidebar";
import { AlertBanner } from "@/components/AlertBanner";
import { useWebSocket } from "@/hooks/useWebSocket";
import { getMe, UserMe } from "@/lib/auth";
import { RealtimeAlertsProvider } from "@/components/realtime/RealtimeAlertsProvider";

function ClientLayoutInner({
  user,
  children,
}: {
  user: UserMe | null;
  children: React.ReactNode;
}) {
  const { lastAlert } = useWebSocket(user?.client_id ?? null);
  const pathname = usePathname();
  const [unreadAlerts, setUnreadAlerts] = useState(0);

  // Increment badge on new WebSocket alert
  useEffect(() => {
    if (lastAlert) setUnreadAlerts((n) => n + 1);
  }, [lastAlert]);

  // Reset badge when user visits the alerts page
  useEffect(() => {
    if (pathname === "/client/alerts") setUnreadAlerts(0);
  }, [pathname]);

  const navWithBadge = CLIENT_NAV.map((item) =>
    item.href === "/client/alerts"
      ? { ...item, badge: unreadAlerts }
      : item
  );

  return (
    <>
      <AlertBanner lastAlert={lastAlert} />
      <div className="min-h-screen bg-gray-50">
        <Sidebar
          userName={user?.name}
          userEmail={user?.email}
          navItems={navWithBadge}
          appName="Monitoramento"
        />
        <div className="lg:pl-64">
          <div className="pt-14 lg:pt-0 min-h-screen">{children}</div>
        </div>
      </div>
    </>
  );
}

export default function ClientLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [user, setUser] = useState<UserMe | null>(null);

  useEffect(() => {
    getMe()
      .then(setUser)
      .catch(() => {});
  }, []);

  return (
    <RealtimeAlertsProvider clientId={user?.client_id ?? null}>
      <ClientLayoutInner user={user}>{children}</ClientLayoutInner>
    </RealtimeAlertsProvider>
  );
}
