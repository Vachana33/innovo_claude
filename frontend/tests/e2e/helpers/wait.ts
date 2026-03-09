import { Page } from "@playwright/test";

/**
 * Wait for a list page to be stable: network idle, then loading indicator gone (if present).
 * Call after navigating to a page that shows a list (funding programs, companies, documents).
 */
export async function waitForListPageStable(
  page: Page,
  loadingTestId: string,
  options?: { networkIdleTimeout?: number; loadingHideTimeout?: number }
): Promise<void> {
  const { networkIdleTimeout = 10_000, loadingHideTimeout = 15_000 } = options ?? {};
  await page.waitForLoadState("networkidle", { timeout: networkIdleTimeout });
  const loading = page.getByTestId(loadingTestId);
  const visible = await loading.isVisible().catch(() => false);
  if (visible) {
    await loading.waitFor({ state: "hidden", timeout: loadingHideTimeout });
  }
}
