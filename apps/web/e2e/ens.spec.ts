import { expect, test } from "@playwright/test";

const hasEnsEnv = Boolean(process.env.NEXT_PUBLIC_ENS_RPC_URL);

test.describe("ENS resolver page", () => {
  test.skip(!hasEnsEnv, "NEXT_PUBLIC_ENS_RPC_URL required");

  test("resolves lifi-quote.goldenmcp.eth agent records", async ({ page, request }) => {
    const probe = await request.get("/api/ens?name=lifi-quote.goldenmcp.eth");
    if (!probe.ok()) {
      const body = await probe.json().catch(() => ({}));
      const msg = typeof body.error === "string" ? body.error : probe.statusText();
      test.skip(true, `ENS live data unavailable on Sepolia — ${msg}`);
    }

    await page.goto("/ens");

    await expect(page.getByRole("heading", { name: "ENS Resolver" })).toBeVisible();

    await page.getByPlaceholder("lifi-quote.goldenmcp.eth").fill("lifi-quote.goldenmcp.eth");
    await page.getByRole("button", { name: "Resolve" }).click();

    const agentContext = page.locator("dt", { hasText: "agent-context" });
    const agentEndpoint = page.locator("dt", { hasText: "agent-endpoint[mcp]" });

    await expect(agentContext.or(agentEndpoint).first()).toBeVisible({ timeout: 30_000 });
  });
});
