import { expect, test } from "@playwright/test";

const hasArcEnv =
  Boolean(process.env.NEXT_PUBLIC_ARC_RPC_URL) &&
  Boolean(process.env.NEXT_PUBLIC_REGISTRY_ADDRESS);

test.describe("leaderboard live data", () => {
  test.skip(!hasArcEnv, "NEXT_PUBLIC_ARC_RPC_URL and NEXT_PUBLIC_REGISTRY_ADDRESS required");

  test("shows lifi row from Arc registry", async ({ page }) => {
    await page.goto("/leaderboard");

    await expect(page.getByRole("heading", { name: "MCP Leaderboard" })).toBeVisible();
    const error = page.locator("p", { hasText: /^Error:/ });
    const empty = page.getByText("No entries — deploy registry and run evals first.");
    if (await error.isVisible()) {
      test.skip(true, `Arc leaderboard unavailable — ${await error.textContent()}`);
    }
    if (await empty.isVisible()) {
      test.skip(true, "Arc registry returned no scored entries in E2E server");
    }
    await expect(page.getByRole("link", { name: "lifi" })).toBeVisible({ timeout: 30_000 });
    await expect(page.locator("tbody tr").filter({ hasText: "lifi" }).first()).toBeVisible();
  });
});
