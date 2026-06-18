import { spawn } from "node:child_process";
import { once } from "node:events";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const isWindows = process.platform === "win32";
const repoRoot = new URL("../../", import.meta.url);
const frontendRoot = new URL("../", import.meta.url);
const lifecycleStatePath = path.join(path.dirname(fileURLToPath(import.meta.url)), "..", ".playwright-managed-servers.json");

export function buildManagedServers() {
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
}

export async function waitForUrl(url, timeoutMs = 120_000) {
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

export function spawnManagedServer(server) {
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

function spawnDetachedManagedServer(server) {
  if (isWindows) {
    return spawnDetachedManagedServerOnWindows(server);
  }

  const child = spawn(server.command, server.args, {
    cwd: server.cwd,
    env: server.env,
    stdio: "ignore",
    shell: false,
    detached: true,
  });

  child.unref();
  return child;
}

function quotePowerShell(value) {
  return `'${String(value).replace(/'/g, "''")}'`;
}

function spawnDetachedManagedServerOnWindows(server) {
  const envAssignments = Object.entries(server.env ?? {})
    .filter(([key, value]) => process.env[key] !== value)
    .map(([key, value]) => `$env:${key}=${quotePowerShell(value)}`)
    .join("; ");
  const argumentList = server.args.map((value) => quotePowerShell(value)).join(", ");
  const script = [
    envAssignments,
    `$argList = @(${argumentList})`,
    `$process = Start-Process -FilePath ${quotePowerShell(server.command)} -ArgumentList $argList -WorkingDirectory ${quotePowerShell(fileURLToPath(server.cwd))} -WindowStyle Hidden -PassThru`,
    "[Console]::Out.WriteLine($process.Id)",
  ]
    .filter(Boolean)
    .join("; ");

  const launcher = spawn("powershell", ["-NoProfile", "-Command", script], {
    stdio: ["ignore", "pipe", "pipe"],
    shell: false,
  });

  let stdout = "";
  let stderr = "";

  return new Promise((resolve, reject) => {
    launcher.stdout?.on("data", (chunk) => {
      stdout += chunk.toString();
    });
    launcher.stderr?.on("data", (chunk) => {
      stderr += chunk.toString();
    });
    launcher.on("error", reject);
    launcher.on("exit", (code) => {
      if (code !== 0) {
        reject(new Error(`Failed to start detached server ${server.name}: ${stderr || `exit code ${code}`}`));
        return;
      }

      const pid = Number.parseInt(stdout.trim(), 10);
      if (!Number.isFinite(pid)) {
        reject(new Error(`Failed to parse detached server pid for ${server.name}: ${stdout || stderr}`));
        return;
      }

      resolve({ pid });
    });
  });
}

async function waitForManagedChildExit(child, timeoutMs = 5_000) {
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

export async function killManagedChild(child) {
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

export async function startManagedServers() {
  const servers = buildManagedServers();
  const children = [];
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

    child.on("exit", (code) => {
      if (!cleanedUp && code && code !== 0) {
        console.error(`${server.name} server exited early with code ${code}.`);
      }
    });

    await waitForUrl(server.url);
  }

  return cleanup;
}

async function killManagedPid(pid) {
  if (!pid) {
    return;
  }

  if (isWindows) {
    await new Promise((resolve) => {
      const killer = spawn("taskkill", ["/PID", String(pid), "/T", "/F"], {
        stdio: "ignore",
        shell: false,
      });
      killer.on("exit", () => resolve());
      killer.on("error", () => resolve());
    });
    return;
  }

  try {
    process.kill(-pid, "SIGKILL");
  } catch {
    // Process tree already exited.
  }
}

export async function startManagedServersForGlobalHooks() {
  const servers = buildManagedServers();
  const startedServers = [];

  for (const server of servers) {
    const child = await spawnDetachedManagedServer(server);
    startedServers.push({
      name: server.name,
      pid: child.pid ?? null,
    });
    await waitForUrl(server.url);
  }

  await fs.writeFile(lifecycleStatePath, JSON.stringify({ servers: startedServers }, null, 2), "utf-8");
}

export async function stopManagedServersForGlobalHooks() {
  let payload;

  try {
    payload = JSON.parse(await fs.readFile(lifecycleStatePath, "utf-8"));
  } catch {
    return;
  }

  const servers = Array.isArray(payload?.servers) ? payload.servers : [];
  await Promise.all(servers.map((server) => killManagedPid(Number(server?.pid) || 0)));
  await fs.rm(lifecycleStatePath, { force: true });
}
