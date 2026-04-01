import { test, expect } from "@playwright/test";

/**
 * AdminGuard E2E tests.
 *
 * These tests verify that admin-only routes redirect non-admin users to /dashboard.
 * They work by injecting localStorage values before page load to simulate a
 * logged-in non-admin session. The redirect is client-side and synchronous,
 * so no server round-trip is needed for the guard check itself.
 *
 * Note: API calls made after the redirect (e.g. project list fetch) will fail
 * with 401 because the injected token is fake, but the URL assertion passes
 * before those calls complete.
 */

const ADMIN_ROUTES = [
  "/alte-vorhabensbeschreibung",
  "/funding-programs",
  "/companies",
  "/admin/knowledge-base",
];

for (const route of ADMIN_ROUTES) {
  test(`non-admin is redirected from ${route} to /dashboard`, async ({ page }) => {
    // Inject a non-admin session into localStorage before the page loads.
    // isAdmin = false → AdminGuard renders <Navigate to="/dashboard" replace />.
    await page.addInitScript(() => {
      localStorage.setItem("innovo_auth_token", "fake.eyJ.token");
      localStorage.setItem("innovo_user_email", "nonadmin@innovo-consulting.de");
      localStorage.setItem("innovo_is_admin", "false");
    });

    await page.goto(route);

    // AdminGuard redirects synchronously during render — URL should be /dashboard.
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 5_000 });
  });
}

test("unauthenticated access to admin route redirects to /login", async ({ page }) => {
  // No localStorage injection — ProtectedRoute handles this redirect.
  await page.goto("/alte-vorhabensbeschreibung");
  await expect(page).toHaveURL(/\/login/, { timeout: 5_000 });
});
