import test from "node:test";
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { once } from "node:events";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const wrapperPath = path.join(__dirname, "playwright-web-server.mjs");
const childFixturePath = path.join(__dirname, "fixtures", "playwright-web-server-child.mjs");

function waitForReady(child, timeoutMs = 5_000) {
  return new Promise((resolve, reject) => {
    let output = "";
    const timeoutId = setTimeout(() => {
      cleanup();
      reject(new Error(`Timed out waiting for fixture readiness. Output: ${output}`));
    }, timeoutMs);

    function cleanup() {
      clearTimeout(timeoutId);
      child.stdout?.off("data", onData);
      child.stderr?.off("data", onData);
    }

    function onData(chunk) {
      output += chunk.toString();
      if (output.includes("child:ready:")) {
        const match = output.match(/child:ready:(\d+)/);
        cleanup();
        resolve(Number(match?.[1]));
      }
    }

    child.stdout?.on("data", onData);
    child.stderr?.on("data", onData);
  });
}

function waitForExit(child, timeoutMs = 5_000) {
  return Promise.race([
    once(child, "exit"),
    new Promise((_, reject) => {
      setTimeout(() => {
        reject(new Error(`Timed out waiting for wrapper exit (pid=${child.pid ?? "unknown"}).`));
      }, timeoutMs);
    }),
  ]);
}

function isProcessAlive(pid) {
  try {
    process.kill(pid, 0);
    return true;
  } catch {
    return false;
  }
}

test("wrapper exits promptly and terminates the wrapped child when stdin closes", async () => {
  const wrapper = spawn(process.execPath, [wrapperPath, process.execPath, childFixturePath], {
    cwd: path.dirname(__dirname),
    stdio: ["pipe", "pipe", "pipe"],
    shell: false,
  });

  const childPid = await waitForReady(wrapper);

  wrapper.stdin?.end();
  const [exitCode, signal] = await waitForExit(wrapper);

  assert.equal(signal, null);
  assert.equal(exitCode, 0);
  assert.equal(isProcessAlive(childPid), false);
});
