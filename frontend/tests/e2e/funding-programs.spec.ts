import { test, expect } from "@playwright/test";
import { loginAsE2EUser } from "./helpers/auth";
import { goToFundingPrograms } from "./helpers/navigation";
import { waitForListPageStable } from "./helpers/wait";

test.describe("Funding Programs", () => {
  test.beforeEach(async ({ page }) => {
    await loginAsE2EUser(page);
    await goToFundingPrograms(page);
    await expect(page.getByTestId("page-funding-programs")).toBeVisible({ timeout: 15_000 });
    await waitForListPageStable(page, "funding-loading");
  });

  test("page shows list and new program button", async ({ page }) => {
    await expect(page.getByTestId("funding-new-program-btn")).toBeVisible();
    await expect(page.getByTestId("funding-search")).toBeVisible();
    const loadingVisible = await page.getByTestId("funding-loading").isVisible().catch(() => false);
    expect(loadingVisible).toBe(false);
    const hasList = await page.getByTestId("funding-programs-list").isVisible().catch(() => false);
    const hasEmpty = await page.getByTestId("funding-empty").isVisible().catch(() => false);
    expect(hasList || hasEmpty).toBe(true);
  });

  test("create new funding program", async ({ page }) => {
    const title = `E2E Program ${crypto.randomUUID()}`;
    await page.getByTestId("funding-new-program-btn").click();
    await expect(page.getByTestId("funding-dialog")).toBeVisible({ timeout: 5_000 });
    await page.getByTestId("funding-form-title").fill(title);
    await page.getByTestId("funding-dialog-submit").click();
    await expect(page.getByTestId("funding-dialog")).not.toBeVisible({ timeout: 10_000 });
    await waitForListPageStable(page, "funding-loading");
    const card = page.getByTestId("funding-program-card").filter({ hasText: title }).first();
    await expect(card).toBeVisible({ timeout: 10_000 });
  });

  test("cancel create dialog", async ({ page }) => {
    await page.getByTestId("funding-new-program-btn").click();
    await expect(page.getByTestId("funding-dialog")).toBeVisible({ timeout: 5_000 });
    await page.getByTestId("funding-dialog-cancel").click();
    await expect(page.getByTestId("funding-dialog")).not.toBeVisible({ timeout: 5_000 });
  });
});
