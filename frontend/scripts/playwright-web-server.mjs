import { spawn } from "node:child_process";

const [executable, ...args] = process.argv.slice(2);

if (!executable) {
  console.error("playwright-web-server requires an executable and its arguments.");
  process.exit(1);
}

const child = spawn(executable, args, {
  cwd: process.cwd(),
  stdio: "inherit",
  shell: false,
});

let shuttingDown = false;

function exitAfterTreeKill() {
  if (!child.pid) {
    process.exit(0);
    return;
  }

  if (process.platform === "win32") {
    const killer = spawn("taskkill", ["/PID", String(child.pid), "/T", "/F"], {
      stdio: "ignore",
      shell: false,
    });
    killer.on("exit", () => process.exit(0));
    killer.on("error", () => process.exit(0));
    return;
  }

  child.kill("SIGTERM");
  setTimeout(() => {
    child.kill("SIGKILL");
    process.exit(0);
  }, 2_000).unref();
}

function shutdown() {
  if (shuttingDown) {
    return;
  }
  shuttingDown = true;
  exitAfterTreeKill();
}

process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);
process.on("SIGHUP", shutdown);

child.on("exit", (code, signal) => {
  if (shuttingDown) {
    process.exit(0);
    return;
  }
  if (signal) {
    process.exit(1);
    return;
  }
  process.exit(code ?? 0);
});

child.on("error", (error) => {
  console.error(error);
  process.exit(1);
});
