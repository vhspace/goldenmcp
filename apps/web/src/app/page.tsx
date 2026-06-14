import { LayoutShell } from "@/components/LayoutShell";
import { LandingPage } from "@/components/landing/LandingPage";
import { landingFontClassName } from "@/lib/landing-fonts";

export default function Home() {
  return (
    <div className={landingFontClassName}>
      <LandingPage />
    </div>
  );
}
