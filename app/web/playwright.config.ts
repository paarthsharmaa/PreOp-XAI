import { defineConfig, devices } from "@playwright/test";

const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || undefined;

export default defineConfig({
  testDir: "./e2e",
  timeout: 45_000,
  fullyParallel: false,
  workers: 2,
  reporter: [["list"]],
  use: {
    baseURL: "http://127.0.0.1:4173",
    ...devices["Desktop Chrome"],
    launchOptions: { executablePath },
  },
  webServer: [
    {
      command: "cd ../.. && uv run --locked --group app uvicorn app.api.main:create_app --factory --host 127.0.0.1 --port 8010",
      url: "http://127.0.0.1:8010/health",
      reuseExistingServer: true,
      timeout: 60_000,
    },
    {
      command: "API_URL=http://127.0.0.1:8010 npx vite preview --host 127.0.0.1 --port 4173 --strictPort",
      url: "http://127.0.0.1:4173",
      reuseExistingServer: true,
    },
    {
      command: "npx vite preview --outDir dist-static --host 127.0.0.1 --port 4174 --strictPort",
      url: "http://127.0.0.1:4174",
      reuseExistingServer: true,
    },
  ],
});
