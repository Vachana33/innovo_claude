import { test, expect } from "@playwright/test";
import { loginAsE2EUser } from "./helpers/auth";
import { goToCompanies } from "./helpers/navigation";
import { waitForListPageStable } from "./helpers/wait";

test.describe("Companies", () => {
  test.beforeEach(async ({ page }) => {
    await loginAsE2EUser(page);
    await goToCompanies(page);
    await expect(page.getByTestId("page-companies")).toBeVisible({ timeout: 15_000 });
    await waitForListPageStable(page, "companies-loading");
  });

  test("page shows list and new company button", async ({ page }) => {
    await expect(page.getByTestId("companies-new-btn")).toBeVisible();
    await expect(page.getByTestId("companies-search")).toBeVisible();
    const loadingVisible = await page.getByTestId("companies-loading").isVisible().catch(() => false);
    expect(loadingVisible).toBe(false);
    const hasList = await page.getByTestId("companies-list").isVisible().catch(() => false);
    const hasEmpty = await page.getByTestId("companies-empty").isVisible().catch(() => false);
    expect(hasList || hasEmpty).toBe(true);
  });

  test("create new company", async ({ page }) => {
    const name = `E2E Company ${crypto.randomUUID()}`;
    await page.getByTestId("companies-new-btn").click();
    await expect(page.getByTestId("company-dialog")).toBeVisible({ timeout: 5_000 });
    await page.getByTestId("company-form-name").fill(name);
    await page.getByTestId("company-dialog-submit").click();
    await expect(page.getByTestId("company-dialog")).not.toBeVisible({ timeout: 10_000 });
    await waitForListPageStable(page, "companies-loading");
    const card = page.getByTestId("company-card").filter({ hasText: name }).first();
    await expect(card).toBeVisible({ timeout: 10_000 });
  });

  test("cancel create dialog", async ({ page }) => {
    await page.getByTestId("companies-new-btn").click();
    await expect(page.getByTestId("company-dialog")).toBeVisible({ timeout: 5_000 });
    await page.getByTestId("company-dialog-cancel").click();
    await expect(page.getByTestId("company-dialog")).not.toBeVisible({ timeout: 5_000 });
  });
});
