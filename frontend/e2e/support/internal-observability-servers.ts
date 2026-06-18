import { spawn, type ChildProcess } from "node:child_process";
import { once } from "node:events";

const isWindows = process.platform === "win32";
const repoRoot = new URL("../../../", import.meta.url);
const frontendRoot = new URL("../../", import.meta.url);

type ManagedServer = {
  name: string;
  cwd: URL;
  url: string;
  command: string;
  args: string[];
  env: NodeJS.ProcessEnv;
};

function buildManagedServers(): ManagedServer[] {
  const e2eAppEnv = process.env.WEEKENDPILOT_E2E_APP_ENV ?? `e2e-${Date.now()}`;

  return [
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
      command: process.execPath,
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
      command: process.execPath,
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
}

async function waitForUrl(url: string, timeoutMs = 120_000) {
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

function spawnManagedServer(server: ManagedServer): ChildProcess {
  const child = spawn(server.command, server.args, {
    cwd: server.cwd,
    env: server.env,
    stdio: ["ignore", "pipe", "pipe"],
    shell: false,
  });

  child.stdout?.on("data", (chunk) => {
    process.stdout.write(chunk);
  });
  child.stderr?.on("data", (chunk) => {
    process.stderr.write(chunk);
  });
  child.unref();
  return child;
}

async function waitForManagedChildExit(child: ChildProcess, timeoutMs = 5_000) {
  if (child.exitCode !== null || child.signalCode !== null) {
    return;
  }

  await Promise.race([
    once(child, "exit"),
    new Promise((_, reject) => {
      setTimeout(() => {
        reject(new Error(`Timed out waiting for managed child ${child.pid ?? "unknown"} to exit.`));
      }, timeoutMs);
    }),
  ]);
}

async function killManagedChild(child: ChildProcess) {
  if (!child.pid) {
    return;
  }

  if (isWindows) {
    await new Promise((resolve) => {
      const killer = spawn("taskkill", ["/PID", String(child.pid), "/T", "/F"], {
        stdio: "ignore",
        shell: false,
      });
      killer.on("exit", () => resolve(undefined));
      killer.on("error", () => resolve(undefined));
    });
    child.stdout?.destroy();
    child.stderr?.destroy();
    return;
  }

  child.kill("SIGTERM");
  try {
    await waitForManagedChildExit(child, 2_000);
  } catch {
    child.kill("SIGKILL");
    await waitForManagedChildExit(child);
  }
  child.stdout?.destroy();
  child.stderr?.destroy();
}

export async function startInternalObservabilityServers() {
  const servers = buildManagedServers();
  const children: ChildProcess[] = [];
  let cleanedUp = false;

  async function cleanup() {
    if (cleanedUp) {
      return;
    }
    cleanedUp = true;
    await Promise.all(children.map((child) => killManagedChild(child)));
  }

  for (const server of servers) {
    const child = spawnManagedServer(server);
    children.push(child);
    await waitForUrl(server.url);
  }

  return cleanup;
}
