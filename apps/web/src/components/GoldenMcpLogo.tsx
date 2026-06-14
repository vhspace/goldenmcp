import Image from "next/image";
import Link from "next/link";

export const GOLDENMCP_LOGO_PATH = "/images/goldenmcp-logo.png";

const HEIGHT = { sm: 28, md: 36, lg: 44 } as const;

interface GoldenMcpLogoProps {
  size?: keyof typeof HEIGHT;
  href?: string;
  className?: string;
  priority?: boolean;
}

export function GoldenMcpLogo({
  size = "md",
  href = "/",
  className,
  priority = false,
}: GoldenMcpLogoProps) {
  const height = HEIGHT[size];

  const image = (
    <Image
      src={GOLDENMCP_LOGO_PATH}
      alt="GoldenMCP"
      width={Math.round(height * 4.2)}
      height={height}
      priority={priority}
      className={className}
      style={{ height, width: "auto" }}
    />
  );

  if (!href) return image;

  return (
    <Link href={href} style={{ display: "inline-flex", alignItems: "center", lineHeight: 0 }}>
      {image}
    </Link>
  );
}
