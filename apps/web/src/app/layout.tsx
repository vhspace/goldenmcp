import { LayoutShell } from "@/components/LayoutShell";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body style={{ fontFamily: "system-ui, sans-serif", margin: 0, background: "#0a0a0f", color: "#e8e8ef" }}>
        <LayoutShell>{children}</LayoutShell>
      </body>
    </html>
  );
}
