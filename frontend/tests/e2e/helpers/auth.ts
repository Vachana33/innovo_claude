import { Page } from "@playwright/test";

/**
 * Get E2E credentials from env. Throws if missing.
 */
export function getE2ECredentials(): { email: string; password: string } {
  const email = process.env.E2E_TEST_EMAIL;
  const password = process.env.E2E_TEST_PASSWORD;
  if (!email || !password) {
    throw new Error("E2E_TEST_EMAIL and E2E_TEST_PASSWORD must be set to run E2E tests");
  }
  return { email, password };
}

/**
 * Navigate to login page and wait for it to be ready.
 */
export async function goToLogin(page: Page): Promise<void> {
  await page.goto("/login");
  await page.getByTestId("login-page").waitFor({ state: "visible", timeout: 15_000 });
}

/**
 * Fill login form and submit. Does not navigate; use goToLogin first if needed.
 */
export async function fillLoginForm(
  page: Page,
  email: string,
  password: string
): Promise<void> {
  await page.getByTestId("login-email").fill(email);
  await page.getByTestId("login-password").fill(password);
  await page.getByTestId("login-submit").click();
}

/**
 * Log in with E2E credentials: go to /login, fill form, submit, wait for app layout.
 * Use after navigating to baseURL or from a clean state.
 */
export async function loginAsE2EUser(page: Page): Promise<void> {
  const { email, password } = getE2ECredentials();
  await goToLogin(page);
  await fillLoginForm(page, email, password);
  await page.getByTestId("layout").waitFor({ state: "visible", timeout: 20_000 });
}
