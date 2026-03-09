import { defineConfig, devices } from "@playwright/test";

/**
 * E2E config for Innovo frontend. baseURL http://localhost:5173.
 * Uses E2E_TEST_EMAIL and E2E_TEST_PASSWORD for login.
 * Run with: npm run test:e2e (or test:e2e:ui / test:e2e:headed).
 */
import * as dotenv from 'dotenv';

dotenv.config({ path: '.env.e2e' });


export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: "html",
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || "http://localhost:5173",
    trace: "on-first-retry",
    actionTimeout: 15_000,
    navigationTimeout: 20_000,
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
  timeout: 60_000,
  expect: { timeout: 10_000 },
});
