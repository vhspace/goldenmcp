"use client";

import { usePathname } from "next/navigation";
import { SiteNav } from "@/components/SiteNav";

export function LayoutShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isLanding = pathname === "/";
  const isDemo = pathname === "/demo" || pathname.startsWith("/demo/");

  if (isLanding || isDemo) {
    return <>{children}</>;
  }

  return (
    <>
      <SiteNav />
      <main style={{ padding: "2rem" }}>{children}</main>
    </>
  );
}
