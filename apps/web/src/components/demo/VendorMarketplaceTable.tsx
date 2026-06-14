import Link from "next/link";
import { goldenScoreBadge, type VendorProfile } from "@/lib/vendors";
import styles from "./demo-dashboard.module.css";

function shortEns(name: string): string {
  if (name.length <= 18) return name;
  return `${name.slice(0, 8)}…${name.slice(-6)}`;
}

export function VendorMarketplaceTable({ vendors }: { vendors: VendorProfile[] }) {
  if (vendors.length === 0) return null;

  return (
    <div className={styles.tableWrap}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>Vendor</th>
            <th>Golden Score</th>
            <th>Capability</th>
            <th>Identity</th>
            <th>Reliability</th>
            <th>Trade</th>
          </tr>
        </thead>
        <tbody>
          {vendors.map((vendor) => {
            const badge = goldenScoreBadge(vendor.goldenScore);
            const initial = (vendor.mcp[0] ?? "M").toUpperCase();
            return (
              <tr key={`${vendor.vendorName}-${vendor.mcp}`}>
                <td>
                  <div className={styles.vendorCell}>
                    <div className={styles.avatar}>{initial}</div>
                    <div>
                      <p className={styles.vendorName}>{vendor.vendorName}</p>
                      <p className={styles.vendorMeta}>
                        {vendor.mcp}
                        {vendor.attested ? " · TEE attested" : ""}
                        {vendor.failed ? " · failed eval" : ""}
                      </p>
                    </div>
                  </div>
                </td>
                <td className={styles.scoreCell}>{badge.percent}%</td>
                <td>
                  <div>{vendor.primaryCapability}</div>
                  <div className={styles.vendorMeta}>{badge.label}</div>
                </td>
                <td>
                  {vendor.ensError ? (
                    <span className={styles.muted}>{vendor.ensError}</span>
                  ) : (
                    <span>{vendor.ensRecords ? shortEns(vendor.vendorName) : "—"}</span>
                  )}
                </td>
                <td>
                  <div>{Math.round(vendor.reliability * 100)}%</div>
                  <div className={styles.vendorMeta}>
                    cost {Math.round(vendor.costEfficiency * 100)}%
                  </div>
                </td>
                <td>
                  <Link
                    href={`/mcp/${vendor.mcp}/${vendor.primaryCapability}`}
                    className={styles.actionBtn}
                  >
                    View MCP
                  </Link>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
