import { spawn } from "node:child_process";

const isWindows = process.platform === "win32";
const repoRoot = new URL("../../", import.meta.url);
const frontendRoot = new URL("../", import.meta.url);
const e2eAppEnv = process.env.WEEKENDPILOT_E2E_APP_ENV ?? `e2e-${Date.now()}`;
const extraArgs = process.argv.slice(2);

const servers = [
  {
    name: "backend",
    cwd: repoRoot,
    url: "http://127.0.0.1:8000/health",
    command: "python",
    args: ["-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1", "--port", "8000"],
    env: {
      ...process.env,
      APP_ENV: e2eAppEnv,
      LANGSMITH_TRACING: "false",
      LOCAL_TRACE_BUFFER_PATH: `var/traces/weekendpilot-${e2eAppEnv}.jsonl`,
    },
  },
  {
    name: "customer",
    cwd: frontendRoot,
    url: "http://127.0.0.1:5173/",
    command: "node",
    args: ["./node_modules/vite/bin/vite.js", "--config", "vite.config.ts", "--host", "127.0.0.1", "--port", "5173"],
    env: {
      ...process.env,
      VITE_API_BASE_URL: "http://127.0.0.1:8000",
    },
  },
  {
    name: "internal",
    cwd: frontendRoot,
    url: "http://127.0.0.1:5174/",
    command: "node",
    args: [
      "./node_modules/vite/bin/vite.js",
      "--config",
      "vite.internal.config.ts",
      "--host",
      "127.0.0.1",
      "--port",
      "5174",
    ],
    env: {
      ...process.env,
      VITE_API_BASE_URL: "http://127.0.0.1:8000",
    },
  },
];

const children = [];
let cleanedUp = false;

async function waitForUrl(url, timeoutMs = 120_000) {
  const startedAt = Date.now();

  while (Date.now() - startedAt < timeoutMs) {
    try {
      const response = await fetch(url);
      if (response.ok) {
        return;
      }
    } catch {
      // Retry until timeout.
    }

    await new Promise((resolve) => setTimeout(resolve, 250));
  }

  throw new Error(`Timed out waiting for ${url}`);
}

function spawnServer(server) {
  const child = spawn(server.command, server.args, {
    cwd: server.cwd,
    env: server.env,
    stdio: "inherit",
    shell: false,
  });

  children.push(child);
  return child;
}

async function killChild(child) {
  if (!child.pid) {
    return;
  }

  if (isWindows) {
    await new Promise((resolve) => {
      const killer = spawn("taskkill", ["/PID", String(child.pid), "/T", "/F"], {
        stdio: "ignore",
        shell: false,
      });
      killer.on("exit", () => resolve());
      killer.on("error", () => resolve());
    });
    return;
  }

  child.kill("SIGTERM");
  await new Promise((resolve) => setTimeout(resolve, 2_000));
  if (!child.killed) {
    child.kill("SIGKILL");
  }
}

async function cleanup() {
  if (cleanedUp) {
    return;
  }
  cleanedUp = true;
  await Promise.all(children.map((child) => killChild(child)));
}

async function main() {
  for (const server of servers) {
    const child = spawnServer(server);
    child.on("exit", (code) => {
      if (!cleanedUp && code && code !== 0) {
        console.error(`${server.name} server exited early with code ${code}.`);
      }
    });
    await waitForUrl(server.url);
  }

  const exitCode = await new Promise((resolve, reject) => {
    const playwright = spawn(
      "node",
      ["./node_modules/playwright/cli.js", "test", ...extraArgs],
      {
        cwd: frontendRoot,
        env: {
          ...process.env,
          PW_E2E_EXTERNAL_SERVERS: "1",
        },
        stdio: "inherit",
        shell: false,
      },
    );

    playwright.on("exit", (code) => resolve(code ?? 1));
    playwright.on("error", reject);
  });

  await cleanup();
  process.exit(exitCode);
}

for (const signal of ["SIGINT", "SIGTERM", "SIGHUP"]) {
  process.on(signal, async () => {
    await cleanup();
    process.exit(1);
  });
}

main().catch(async (error) => {
  console.error(error);
  await cleanup();
  process.exit(1);
});
