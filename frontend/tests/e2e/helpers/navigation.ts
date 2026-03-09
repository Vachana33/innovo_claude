import { Page } from "@playwright/test";

/**
 * Navigate to a protected page by clicking the sidebar link.
 * Assumes user is already logged in (layout visible).
 */
export async function navigateTo(page: Page, path: string): Promise<void> {
  const testId = `nav-${path.replace(/^\//, "").replace(/\//g, "-")}`;
  await page.getByTestId(testId).click();
  await page.waitForURL((url) => url.pathname === path || url.pathname.startsWith(path + "/"), {
    timeout: 15_000,
  });
}

export async function goToDashboard(page: Page): Promise<void> {
  await navigateTo(page, "/dashboard");
}

export async function goToFundingPrograms(page: Page): Promise<void> {
  await navigateTo(page, "/funding-programs");
}

export async function goToCompanies(page: Page): Promise<void> {
  await navigateTo(page, "/companies");
}

export async function goToDocuments(page: Page): Promise<void> {
  await navigateTo(page, "/documents");
}

export async function goToTemplates(page: Page): Promise<void> {
  await navigateTo(page, "/templates");
}

export async function goToAlteVorhabensbeschreibung(page: Page): Promise<void> {
  await navigateTo(page, "/alte-vorhabensbeschreibung");
}
