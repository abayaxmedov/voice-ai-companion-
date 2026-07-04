// Voice-only Uzbek AI companion — Electron main process.
// Responsibilities (TZ 7/9.2): start/stop the local orchestrator and avatar
// bridge, wait for /health, manage macOS mic permission, open the avatar window.

const { app, BrowserWindow, session, ipcMain, systemPreferences } = require("electron");
const { spawn } = require("child_process");
const http = require("http");
const path = require("path");

const REPO_ROOT = path.resolve(__dirname, "..", "..");
const ORCHESTRATOR_URL = "http://127.0.0.1:8765";
const HEALTH_TIMEOUT_MS = 30000;
const HEALTH_POLL_MS = 500;

/** @type {import("child_process").ChildProcess[]} */
const children = [];
let mainWindow = null;

function spawnPython(scriptRelPath, name) {
  const child = spawn("python3", [path.join(REPO_ROOT, scriptRelPath)], {
    cwd: REPO_ROOT,
    stdio: ["ignore", "pipe", "pipe"],
    env: { ...process.env },
  });
  child.stdout.on("data", (data) => process.stdout.write(`[${name}] ${data}`));
  child.stderr.on("data", (data) => process.stderr.write(`[${name}] ${data}`));
  child.on("exit", (code) => {
    console.log(`[${name}] exited with code ${code}`);
  });
  children.push(child);
  return child;
}

function fetchHealthOnce() {
  return new Promise((resolve) => {
    const req = http.get(`${ORCHESTRATOR_URL}/health`, { timeout: 2000 }, (res) => {
      let body = "";
      res.on("data", (chunk) => (body += chunk));
      res.on("end", () => {
        try {
          resolve({ ok: res.statusCode === 200, health: JSON.parse(body) });
        } catch {
          resolve({ ok: false });
        }
      });
    });
    req.on("error", () => resolve({ ok: false }));
    req.on("timeout", () => {
      req.destroy();
      resolve({ ok: false });
    });
  });
}

async function waitForHealth() {
  const deadline = Date.now() + HEALTH_TIMEOUT_MS;
  while (Date.now() < deadline) {
    const result = await fetchHealthOnce();
    if (result.ok) return result.health;
    await new Promise((r) => setTimeout(r, HEALTH_POLL_MS));
  }
  return null;
}

async function ensureBackend() {
  // Reuse an already-running orchestrator (e.g. run_stack.py) if present.
  const existing = await fetchHealthOnce();
  if (existing.ok) return existing.health;

  spawnPython(path.join("scripts", "dev", "run_orchestrator.py"), "orchestrator");
  spawnPython(path.join("scripts", "dev", "run_avatar_bridge.py"), "avatar-bridge");
  return waitForHealth();
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1160,
    height: 780,
    minWidth: 900,
    minHeight: 620,
    title: "Ovozli Hamroh",
    backgroundColor: "#0b0d14",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  mainWindow.loadFile(path.join(__dirname, "renderer", "index.html"));
  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

function stopChildren() {
  for (const child of children) {
    try {
      child.kill("SIGTERM");
    } catch {
      // already dead
    }
  }
}

app.whenReady().then(async () => {
  // Microphone permission (macOS): required for the voice-only product.
  if (process.platform === "darwin" && systemPreferences.askForMediaAccess) {
    try {
      await systemPreferences.askForMediaAccess("microphone");
    } catch (err) {
      console.error("Microphone permission request failed:", err);
    }
  }
  session.defaultSession.setPermissionRequestHandler((_wc, permission, callback) => {
    callback(permission === "media");
  });

  ipcMain.handle("backend:ensure", async () => {
    const health = await ensureBackend();
    return { ready: Boolean(health), health };
  });

  createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  stopChildren();
  app.quit();
});

app.on("before-quit", stopChildren);
process.on("exit", stopChildren);
