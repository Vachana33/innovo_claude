import { test, expect } from "@playwright/test";
import { loginAsE2EUser } from "./helpers/auth";
import { goToDocuments, goToCompanies } from "./helpers/navigation";
import { waitForListPageStable } from "./helpers/wait";

test.describe("Documents", () => {
  test.beforeEach(async ({ page }) => {
    await loginAsE2EUser(page);
    await goToDocuments(page);
    await expect(page.getByTestId("page-documents")).toBeVisible({ timeout: 15_000 });
    await waitForListPageStable(page, "documents-loading");
  });

  test("page shows list and new document button", async ({ page }) => {
    await expect(page.getByTestId("documents-new-btn")).toBeVisible();
    await expect(page.getByTestId("documents-search")).toBeVisible();
    const loadingVisible = await page.getByTestId("documents-loading").isVisible().catch(() => false);
    expect(loadingVisible).toBe(false);
    const hasList = await page.getByTestId("documents-list").isVisible().catch(() => false);
    const hasEmpty = await page.getByTestId("documents-empty").isVisible().catch(() => false);
    expect(hasList || hasEmpty).toBe(true);
  });

  test("open create document dialog and cancel", async ({ page }) => {
    await page.getByTestId("documents-new-btn").click();
    await expect(page.getByTestId("document-create-dialog")).toBeVisible({ timeout: 5_000 });
    await expect(page.getByTestId("document-create-company")).toBeVisible();
    await expect(page.getByTestId("document-create-program")).toBeVisible();
    await page.getByTestId("document-create-cancel").click();
    await expect(page.getByTestId("document-create-dialog")).not.toBeVisible({ timeout: 5_000 });
  });

  test("create document draft opens editor", async ({ page }) => {
    await goToCompanies(page);
    await expect(page.getByTestId("page-companies")).toBeVisible({ timeout: 10_000 });
    await waitForListPageStable(page, "companies-loading");
    const hasCompany = await page.getByTestId("company-card").count() > 0;
    if (!hasCompany) {
      await page.getByTestId("companies-new-btn").click();
      await expect(page.getByTestId("company-dialog")).toBeVisible({ timeout: 5_000 });
      await page.getByTestId("company-form-name").fill(`E2E Doc Company ${crypto.randomUUID()}`);
      await page.getByTestId("company-dialog-submit").click();
      await expect(page.getByTestId("company-dialog")).not.toBeVisible({ timeout: 10_000 });
      await waitForListPageStable(page, "companies-loading");
    }

    await goToDocuments(page);
    await expect(page.getByTestId("page-documents")).toBeVisible({ timeout: 10_000 });
    await waitForListPageStable(page, "documents-loading");
    await page.getByTestId("documents-new-btn").click();
    await expect(page.getByTestId("document-create-dialog")).toBeVisible({ timeout: 5_000 });

    const form = page.getByTestId("document-create-form");

    // Company is mandatory: always select first available company
    await form.getByTestId("document-create-company").selectOption({ index: 1 });

    // Template: try to select a valid template; if so, funding program is required by frontend
    const templateTypeSelect = form.locator("select").nth(2);
    const templateValueSelect = form.locator("select").nth(3);

    await templateTypeSelect.selectOption("system");
    await templateValueSelect.waitFor({ state: "visible", timeout: 3_000 }).catch(() => {});
    const systemTemplateOptionCount = await templateValueSelect.locator("option").count();
    const firstSystemOptionDisabled = await templateValueSelect
      .locator("option")
      .nth(1)
      .getAttribute("disabled")
      .catch(() => null);

    const hasSystemTemplate = systemTemplateOptionCount > 1 && !firstSystemOptionDisabled;
    if (hasSystemTemplate) {
      await templateValueSelect.selectOption({ index: 1 });
      await form.getByTestId("document-create-program").selectOption({ index: 1 });
    } else {
      await templateTypeSelect.selectOption("user");
      await templateValueSelect.waitFor({ state: "visible", timeout: 2_000 }).catch(() => {});
      const userOptionCount = await templateValueSelect.locator("option").count();
      const firstUserOptionDisabled = await templateValueSelect
        .locator("option")
        .nth(1)
        .getAttribute("disabled")
        .catch(() => null);
      const hasUserTemplate = userOptionCount > 1 && !firstUserOptionDisabled;
      if (hasUserTemplate) {
        await templateValueSelect.selectOption({ index: 1 });
        await form.getByTestId("document-create-program").selectOption({ index: 1 });
      } else {
        await templateTypeSelect.selectOption("");
      }
    }

    // Title is mandatory for handleCreateDraft to proceed (first guard)
    await page.getByTestId("document-create-title").fill(`E2E Title ${crypto.randomUUID()}`);

    await form.getByTestId("document-create-submit").click();

    await expect(page).toHaveURL(/\/editor\/\d+\/vorhaben/, { timeout: 15_000 });
    await expect(page.getByTestId("editor-page")).toBeVisible({ timeout: 10_000 });
  });
});

test.describe("Editor (Vorhabensbeschreibung)", () => {
  test("editor loads and shows sidebar and content area", async ({ page }) => {
    await loginAsE2EUser(page);
    await goToCompanies(page);
    await expect(page.getByTestId("page-companies")).toBeVisible({ timeout: 15_000 });
    await waitForListPageStable(page, "companies-loading");
    if ((await page.getByTestId("company-card").count()) === 0) {
      await page.getByTestId("companies-new-btn").click();
      await expect(page.getByTestId("company-dialog")).toBeVisible({ timeout: 5_000 });
      await page.getByTestId("company-form-name").fill(`E2E Editor Company ${crypto.randomUUID()}`);
      await page.getByTestId("company-dialog-submit").click();
      await expect(page.getByTestId("company-dialog")).not.toBeVisible({ timeout: 10_000 });
      await waitForListPageStable(page, "companies-loading");
    }

    await goToDocuments(page);
    await expect(page.getByTestId("page-documents")).toBeVisible({ timeout: 10_000 });
    await waitForListPageStable(page, "documents-loading");
    await page.getByTestId("documents-new-btn").click();
    await expect(page.getByTestId("document-create-dialog")).toBeVisible({ timeout: 5_000 });

    const form = page.getByTestId("document-create-form");
    await form.getByTestId("document-create-company").selectOption({ index: 1 });

    const templateTypeSelect = form.locator("select").nth(2);
    const templateValueSelect = form.locator("select").nth(3);
    await templateTypeSelect.selectOption("system");
    await templateValueSelect.waitFor({ state: "visible", timeout: 3_000 }).catch(() => {});
    const systemTemplateOptionCount = await templateValueSelect.locator("option").count();
    const firstSystemOptionDisabled = await templateValueSelect
      .locator("option")
      .nth(1)
      .getAttribute("disabled")
      .catch(() => null);
    const hasSystemTemplate = systemTemplateOptionCount > 1 && !firstSystemOptionDisabled;
    if (hasSystemTemplate) {
      await templateValueSelect.selectOption({ index: 1 });
      await form.getByTestId("document-create-program").selectOption({ index: 1 });
    } else {
      await templateTypeSelect.selectOption("user");
      await templateValueSelect.waitFor({ state: "visible", timeout: 2_000 }).catch(() => {});
      const userOptionCount = await templateValueSelect.locator("option").count();
      const firstUserOptionDisabled = await templateValueSelect
        .locator("option")
        .nth(1)
        .getAttribute("disabled")
        .catch(() => null);
      if (userOptionCount > 1 && !firstUserOptionDisabled) {
        await templateValueSelect.selectOption({ index: 1 });
        await form.getByTestId("document-create-program").selectOption({ index: 1 });
      } else {
        await templateTypeSelect.selectOption("");
      }
    }

    // Title is mandatory for handleCreateDraft to proceed (first guard)
    await page.getByTestId("document-create-title").fill(`E2E Title ${crypto.randomUUID()}`);

    await form.getByTestId("document-create-submit").click();

    await expect(page).toHaveURL(/\/editor\/\d+\/vorhaben/, { timeout: 15_000 });
    await expect(page.getByTestId("editor-page")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByTestId("editor-sidebar")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByTestId("editor-company-name")).toBeVisible();
    await expect(page.getByTestId("editor-main-area")).toBeVisible();

    const loading = page.getByTestId("editor-loading");
    if (await loading.isVisible().catch(() => false)) {
      await loading.waitFor({ state: "hidden", timeout: 25_000 });
    }
    await expect(page.getByTestId("editor-document-box")).toBeVisible({ timeout: 5_000 });
  });
});
