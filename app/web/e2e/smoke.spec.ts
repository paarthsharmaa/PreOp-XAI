import { expect, test, type Page } from "@playwright/test";

const PAGES = ["/#/", "/#/findings", "/#/explorer", "/#/methods", "/#/team"];
const NOTICE = "Research prototype, not for clinical use.";

function trackErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  return errors;
}

for (const path of PAGES) {
  test(`renders ${path} with the footer notice and no errors`, async ({ page }) => {
    const errors = trackErrors(page);
    await page.goto(path);
    await expect(page.getByRole("contentinfo").filter({ hasText: NOTICE })).toBeVisible();
    await expect(page.locator("h1")).toBeVisible();
    await page.waitForLoadState("networkidle");
    expect(errors).toEqual([]);
  });

  test(`has no horizontal overflow on a phone at ${path}`, async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(path);
    await page.waitForLoadState("networkidle");
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow).toBeLessThanOrEqual(0);
  });
}

test("explorer explains a patient and responds to a what-if change", async ({ page }) => {
  await page.goto("/#/explorer");
  const risk = page.getByTestId("risk-value").first();
  await expect(risk).toBeVisible();
  await expect(page.getByTestId("plain-language")).toContainText("of the top 3 drivers");
  await page.waitForTimeout(600);
  const before = await risk.innerText();
  await page.getByRole("radiogroup", { name: "ASA class" }).getByRole("radio", { name: "V", exact: true }).click();
  await expect(page.getByText("What-if mode")).toBeVisible();
  await expect(risk).not.toHaveText(before);
  await page.getByRole("button", { name: "Reset inputs" }).click();
  await expect(risk).toHaveText(before);
});

test("missing checkbox sends a missing lab", async ({ page }) => {
  await page.goto("/#/explorer");
  await expect(page.getByTestId("risk-value").first()).toBeVisible();
  await page.getByLabel("Sodium missing").check();
  await expect(page.getByTestId("plain-language")).toContainText("1 of 7 labs are missing");
});

test("out-of-range input shows a clear error", async ({ page }) => {
  await page.goto("/#/explorer");
  await expect(page.getByTestId("risk-value").first()).toBeVisible();
  await page.locator("#input-sodium").fill("500");
  await expect(page.getByRole("alert").first()).toContainText("Sodium must be between");
});

test("VitalDB patient shows the miscalibration caveat and hides the outcome until asked", async ({ page }) => {
  await page.goto("/#/explorer");
  await expect(page.getByTestId("risk-value").first()).toBeVisible();
  await page.getByLabel("Example patient").selectOption("vitaldb-01");
  await expect(page.getByText("miscalibrated at VitalDB")).toBeVisible();
  await expect(page.getByTestId("observed-outcome")).toHaveCount(0);
  await page.getByRole("button", { name: "Reveal outcome" }).click();
  await expect(page.getByTestId("observed-outcome")).toBeVisible();
});

test("static build shows findings and asks to run the explorer locally", async ({ page }) => {
  const requests: string[] = [];
  page.on("request", (request) => requests.push(request.url()));
  await page.goto("http://127.0.0.1:4174/#/findings");
  await expect(page.getByRole("heading", { name: "ROC curve" })).toBeVisible();
  await page.goto("http://127.0.0.1:4174/#/explorer");
  await expect(page.getByRole("heading", { name: "Run locally for the live demo" })).toBeVisible();
  await page.waitForLoadState("networkidle");
  expect(requests.filter((url) => url.includes("/api/"))).toEqual([]);
});
