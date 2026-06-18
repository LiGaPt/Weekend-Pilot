import { spawn } from "node:child_process";

const [executable, ...args] = process.argv.slice(2);

if (!executable) {
  console.error("playwright-web-server requires an executable and its arguments.");
  process.exit(1);
}

const child = spawn(executable, args, {
  cwd: process.cwd(),
  stdio: ["ignore", "pipe", "pipe"],
  shell: false,
});

let shuttingDown = false;

child.stdout?.on("data", (chunk) => {
  process.stdout.write(chunk);
});

child.stderr?.on("data", (chunk) => {
  process.stderr.write(chunk);
});

function closeChildStreams() {
  child.stdout?.destroy();
  child.stderr?.destroy();
}

function exitAfterTreeKill() {
  if (!child.pid) {
    closeChildStreams();
    process.exit(0);
    return;
  }

  if (process.platform === "win32") {
    const killer = spawn("taskkill", ["/PID", String(child.pid), "/T", "/F"], {
      stdio: "ignore",
      detached: true,
      shell: false,
    });
    let finished = false;

    const finalize = () => {
      if (finished) {
        return;
      }
      finished = true;
      closeChildStreams();
      process.exit(0);
    };

    killer.unref();
    killer.on("exit", finalize);
    killer.on("error", finalize);
    setTimeout(finalize, 250).unref();
    return;
  }

  child.kill("SIGTERM");
  setTimeout(() => {
    child.kill("SIGKILL");
    closeChildStreams();
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

if (process.stdin && !process.stdin.isTTY) {
  process.stdin.on("end", shutdown);
  process.stdin.on("close", shutdown);
  process.stdin.resume();
}

child.on("exit", (code, signal) => {
  closeChildStreams();
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
