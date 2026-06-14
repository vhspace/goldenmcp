import { fetchVendorProfiles } from "@/lib/data";
import { DemoDashboardLayout } from "@/components/demo/DemoDashboardLayout";
import { VendorMarketplaceTable } from "@/components/demo/VendorMarketplaceTable";
import styles from "@/components/demo/demo-dashboard.module.css";
import { ExecutionSandbox } from "@/components/ExecutionSandbox";
import { GOLDEN_SCORE_THRESHOLDS, METER_THRESHOLDS, type VendorProfile } from "@/lib/vendors";

export const dynamic = "force-dynamic";

function DemoRightRail() {
  return (
    <>
      <div className={`${styles.railCard} ${styles.railCardGold}`}>
        <p className={styles.railTitle}>AI-Powered Risk Control</p>
        <p className={styles.railText}>
          Chainlink CAI attestation in TEE — inference IDs and transcript hashes written to Arc
          registry.
        </p>
        <a className={styles.railLink} href="#vendors">
          View vendors ↓
        </a>
      </div>
      <div className={styles.railCard}>
        <p className={styles.railTitle}>x402 Marketplace</p>
        <p className={styles.railText}>
          Lookup returns HTTP 402 until USDC settles on Arc testnet — live micropayment gate, not a
          mock.
        </p>
      </div>
      <div className={styles.railCard}>
        <p className={styles.railTitle}>Score thresholds</p>
        <p className={styles.railText}>
          Excellent ≥ {GOLDEN_SCORE_THRESHOLDS.excellentMin * 100}% · Good ≥{" "}
          {GOLDEN_SCORE_THRESHOLDS.goodMin * 100}% · Meters green ≥ {METER_THRESHOLDS.greenMin * 100}
          %
        </p>
      </div>
    </>
  );
}

export default async function DemoPage() {
  let vendors: VendorProfile[] = [];
  let error = "";

  try {
    vendors = await fetchVendorProfiles();
  } catch (e) {
    error = e instanceof Error ? e.message : String(e);
  }

  return (
    <DemoDashboardLayout rightRail={<DemoRightRail />}>
      <ExecutionSandbox />

      <section id="vendors" style={{ marginTop: "1rem" }}>
        <h2 className={styles.panelTitle}>Global Overview — MCP Vendors</h2>
        <p className={styles.panelSub}>
          Ranked by Golden Score from live Arc registry reads and Walrus eval manifests.
        </p>

        {error && (
          <div className={styles.errorBanner}>
            <strong>Marketplace unavailable</strong>
            <p style={{ margin: "0.35rem 0 0", fontFamily: "monospace" }}>{error}</p>
          </div>
        )}

        {vendors.length === 0 && !error && (
          <p className={styles.panelSub}>No registered vendors — run evals and register MCPs on Arc first.</p>
        )}

        <VendorMarketplaceTable vendors={vendors} />
      </section>
    </DemoDashboardLayout>
  );
}
