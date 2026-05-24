import { defineConfig, devices } from "@playwright/test";

const e2eAppEnv = process.env.WEEKENDPILOT_E2E_APP_ENV ?? `e2e-${Date.now()}`;
const externalServersManaged = process.env.PW_E2E_EXTERNAL_SERVERS === "1";

export default defineConfig({
  testDir: "./e2e",
  timeout: 120_000,
  expect: {
    timeout: 10_000,
  },
  workers: 1,
  use: {
    baseURL: "http://127.0.0.1:5173",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off",
  },
  projects: [
    {
      name: "desktop-chromium",
      use: {
        ...devices["Desktop Chrome"],
        channel: "chrome",
        launchOptions: {
          args: ["--single-process"],
        },
      },
    },
    {
      name: "mobile-chromium",
      use: {
        ...devices["Pixel 5"],
        channel: "chrome",
        launchOptions: {
          args: ["--single-process"],
        },
      },
    },
  ],
  webServer: externalServersManaged
    ? undefined
    : [
    {
      command: "node ./frontend/scripts/playwright-web-server.mjs python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000",
      cwd: "..",
      url: "http://127.0.0.1:8000/health",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      gracefulShutdown: {
        signal: "SIGTERM",
        timeout: 5_000,
      },
      env: {
        ...process.env,
        APP_ENV: e2eAppEnv,
        LANGSMITH_TRACING: "false",
        LOCAL_TRACE_BUFFER_PATH: `var/traces/weekendpilot-${e2eAppEnv}.jsonl`,
      },
    },
    {
      command: "node ./scripts/playwright-web-server.mjs node ./node_modules/vite/bin/vite.js --config vite.config.ts --host 127.0.0.1 --port 5173",
      cwd: ".",
      url: "http://127.0.0.1:5173",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      gracefulShutdown: {
        signal: "SIGTERM",
        timeout: 5_000,
      },
      env: {
        ...process.env,
        VITE_API_BASE_URL: "http://127.0.0.1:8000",
      },
    },
    {
      command: "node ./scripts/playwright-web-server.mjs node ./node_modules/vite/bin/vite.js --config vite.internal.config.ts --host 127.0.0.1 --port 5174",
      cwd: ".",
      url: "http://127.0.0.1:5174",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      gracefulShutdown: {
        signal: "SIGTERM",
        timeout: 5_000,
      },
      env: {
        ...process.env,
        VITE_API_BASE_URL: "http://127.0.0.1:8000",
      },
    },
  ],
});
