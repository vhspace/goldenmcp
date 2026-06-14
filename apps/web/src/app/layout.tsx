import type { Metadata } from "next";
import { LayoutShell } from "@/components/LayoutShell";

export const metadata: Metadata = {
  title: "GoldenMCP",
  description: "Web3 MCP evaluation marketplace — Walrus scores, ENS identity, x402 on Arc.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body style={{ fontFamily: "system-ui, sans-serif", margin: 0, background: "#0a0a0f", color: "#e8e8ef" }}>
        <LayoutShell>{children}</LayoutShell>
      </body>
    </html>
  );
}
