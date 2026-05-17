"use client";

import { useEffect, useState } from "react";
import { Sidebar } from "@/components/ui/Sidebar";
import { getMe, UserMe } from "@/lib/auth";

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserMe | null>(null);

  useEffect(() => {
    getMe()
      .then(setUser)
      .catch(() => {});
  }, []);

  return (
    <div className="min-h-screen bg-gray-50">
      <Sidebar userName={user?.name} userEmail={user?.email} />
      <div className="lg:pl-64">
        <div className="pt-14 lg:pt-0 min-h-screen">{children}</div>
      </div>
    </div>
  );
}
