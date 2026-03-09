import { test, expect } from "@playwright/test";
import { goToLogin, fillLoginForm, getE2ECredentials, loginAsE2EUser } from "./helpers/auth";

test.describe("Auth", () => {
  test("login page has form and mode switch", async ({ page }) => {
    await goToLogin(page);
    await expect(page.getByTestId("login-page")).toBeVisible();
    await expect(page.getByTestId("login-box")).toBeVisible();
    await expect(page.getByTestId("login-tab")).toBeVisible();
    await expect(page.getByTestId("signup-tab")).toBeVisible();
    await expect(page.getByTestId("login-email")).toBeVisible();
    await expect(page.getByTestId("login-password")).toBeVisible();
    await expect(page.getByTestId("login-submit")).toBeVisible();
  });

  test("login with valid E2E credentials redirects to app", async ({ page }) => {
    await loginAsE2EUser(page);
    await expect(page.getByTestId("layout")).toBeVisible();
    await expect(page).toHaveURL(/\/(dashboard|funding-programs|companies|documents|$)/);
  });

  test("invalid credentials show error", async ({ page }) => {
    await goToLogin(page);
    await fillLoginForm(page, "wrong@innovo-consulting.de", "wrongpass");
    await expect(page.getByTestId("login-error")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByTestId("login-page")).toBeVisible();
  });

  test("logout returns to login", async ({ page }) => {
    await loginAsE2EUser(page);
    await expect(page.getByTestId("layout")).toBeVisible();
    await page.getByTestId("logout-btn").click();
    await expect(page.getByTestId("login-page")).toBeVisible({ timeout: 10_000 });
    await expect(page).toHaveURL(/\/login/);
  });
});
