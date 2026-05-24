import { expect, test } from "@playwright/test";

test.describe("internal observability surface", () => {
  test.beforeEach(({}, testInfo) => {
    test.skip(testInfo.project.name !== "desktop-chromium", "Internal surface smoke runs once on desktop.");
  });

  test("loads on the dedicated internal frontend origin", async ({ page }) => {
    await page.goto("http://127.0.0.1:5174/");

    await expect(page.getByRole("heading", { name: "Internal Observability Review" })).toBeVisible();
    await expect(page.getByRole("textbox", { name: "Run ID" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Load Run" })).toBeVisible();
    await expect(page.getByTestId("start-button")).toHaveCount(0);
    await expect(page.getByTestId("read-profile-select")).toHaveCount(0);
  });
});
