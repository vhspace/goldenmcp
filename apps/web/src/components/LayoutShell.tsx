"use client";

import { usePathname } from "next/navigation";
import { SiteNav } from "@/components/SiteNav";

export function LayoutShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isLanding = pathname === "/";

  if (isLanding) {
    return <>{children}</>;
  }

  return (
    <>
      <SiteNav />
      <main style={{ padding: "2rem" }}>{children}</main>
    </>
  );
}
