import { expect, test } from "@playwright/test";

test.describe("home page smoke", () => {
  test("shows GoldenMCP heading and nav links", async ({ page }) => {
    await page.goto("/");

    const nav = page.getByRole("navigation");
    await expect(page.getByRole("main").getByRole("heading", { name: "GoldenMCP" })).toBeVisible();
    await expect(nav.getByRole("link", { name: "GoldenMCP" })).toBeVisible();
    await expect(nav.getByRole("link", { name: "Marketplace" })).toBeVisible();
    await expect(nav.getByRole("link", { name: "Leaderboard" })).toBeVisible();
    await expect(nav.getByRole("link", { name: "ENS Resolver" })).toBeVisible();
    await expect(page.getByRole("main").getByRole("link", { name: "Marketplace" })).toBeVisible();
    await expect(page.getByRole("main").getByRole("link", { name: "Leaderboard" })).toBeVisible();
    await expect(page.getByRole("main").getByRole("link", { name: "ENS Resolver" })).toBeVisible();
  });
});
