import { spawn } from "node:child_process";
import { startManagedServers } from "./playwright-server-lifecycle.js";

const frontendRoot = new URL("../", import.meta.url);
const extraArgs = process.argv.slice(2);
let cleanedUp = false;
let cleanupServers = async () => {};

async function cleanup() {
  if (cleanedUp) {
    return;
  }
  cleanedUp = true;
  await cleanupServers();
}

async function main() {
  cleanupServers = await startManagedServers();

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
