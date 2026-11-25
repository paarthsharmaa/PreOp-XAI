import { mkdirSync } from "node:fs";
import { resolve } from "node:path";
import { expect, test } from "@playwright/test";

const OUT = resolve(process.cwd(), process.env.SCREENSHOT_DIR ?? "../../docs/screenshots");
const PAGES = [
  ["overview", "/#/"],
  ["findings", "/#/findings"],
  ["explorer", "/#/explorer"],
  ["methods", "/#/methods"],
  ["team", "/#/team"],
] as const;

test.skip(!process.env.SCREENSHOTS, "Set SCREENSHOTS=1 to capture.");

for (const [viewport, width, height] of [["desktop", 1360, 900], ["mobile", 390, 844]] as const) {
  for (const [name, path] of PAGES) {
    test(`${name} ${viewport}`, async ({ page }) => {
      mkdirSync(OUT, { recursive: true });
      await page.setViewportSize({ width, height });
      await page.goto(path);
      if (name === "explorer") await expect(page.getByTestId("risk-value").first()).toBeVisible();
      await page.waitForLoadState("networkidle");
      await page.waitForTimeout(700);
      await page.screenshot({ path: `${OUT}/${name}-${viewport}.png`, fullPage: true });
    });
  }
}

test("explorer what-if", async ({ page }) => {
  mkdirSync(OUT, { recursive: true });
  await page.setViewportSize({ width: 1360, height: 900 });
  await page.goto("/#/explorer");
  await expect(page.getByTestId("risk-value").first()).toBeVisible();
  await page.getByLabel("Example patient").selectOption("synthetic-frail");
  await expect(page.getByTestId("plain-language")).toContainText("ASA IV");
  await page.waitForTimeout(500);
  await page.getByRole("radiogroup", { name: "ASA class" }).getByRole("radio", { name: "II", exact: true }).click();
  await expect(page.getByText("What-if mode")).toBeVisible();
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(800);
  await page.screenshot({ path: `${OUT}/explorer-whatif-desktop.png`, fullPage: true });
});
