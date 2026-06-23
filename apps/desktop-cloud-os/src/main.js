const { app, BrowserWindow, Menu, Tray, dialog, shell } = require("electron");
const { spawn } = require("child_process");
const fs = require("fs");
const http = require("http");
const path = require("path");

const PORT = Number(process.env.CLOUD_OS_DESKTOP_PORT || 8790);
const HUB_URL = `http://127.0.0.1:${PORT}/`;
const APP_ROOT = path.resolve(__dirname, "..");
const SOURCE_ROOT = path.resolve(APP_ROOT, "..");
const DEV_DECISION_HUB = path.join(SOURCE_ROOT, "decision-hub");
const PROD_DECISION_HUB = path.join(process.resourcesPath || "", "decision-hub");
const DECISION_HUB_ROOT = app.isPackaged
  ? PROD_DECISION_HUB
  : fs.existsSync(path.join(DEV_DECISION_HUB, "server.ps1"))
  ? DEV_DECISION_HUB
  : PROD_DECISION_HUB;
const LOG_DIR = path.join(app.getPath("userData"), "logs");
const LOG_PATH = path.join(LOG_DIR, "desktop-service.log");
const ICON_PATH = app.isPackaged
  ? path.join(process.resourcesPath || "", "app.asar", "assets", "cloud-os.ico")
  : path.join(APP_ROOT, "assets", "cloud-os.ico");
const RESOURCE_LOG_PATH = app.isPackaged && process.resourcesPath
  ? path.join(process.resourcesPath, "desktop-service.log")
  : null;

let mainWindow;
let tray;
let hubProcess;
let restartAttempts = 0;
let isQuitting = false;

function appendLog(message) {
  const line = `${new Date().toISOString()} ${message}\n`;
  fs.mkdirSync(LOG_DIR, { recursive: true });
  fs.appendFileSync(LOG_PATH, line, "utf8");
  if (RESOURCE_LOG_PATH) {
    try {
      fs.appendFileSync(RESOURCE_LOG_PATH, line, "utf8");
    } catch {
      // User data log remains authoritative when resources are read-only.
    }
  }
}

function waitForHub(timeoutMs = 30000) {
  const startedAt = Date.now();
  return new Promise((resolve, reject) => {
    const probe = () => {
      const request = http.get(HUB_URL, (response) => {
        response.resume();
        resolve();
      });
      request.on("error", () => {
        if (Date.now() - startedAt > timeoutMs) {
          reject(new Error("Decision Hub did not start in time."));
          return;
        }
        setTimeout(probe, 700);
      });
      request.setTimeout(1200, () => request.destroy());
    };
    probe();
  });
}

function startDecisionHub() {
  if (hubProcess && !hubProcess.killed) return;
  const scriptPath = path.join(DECISION_HUB_ROOT, "server.ps1");
  if (!fs.existsSync(scriptPath)) {
    throw new Error(`Decision Hub server not found: ${scriptPath}`);
  }

  appendLog(`Starting Decision Hub on port ${PORT}`);
  appendLog(`Decision Hub root: ${DECISION_HUB_ROOT}`);
  appendLog(`Decision Hub script: ${scriptPath}`);
  hubProcess = spawn(
    "powershell.exe",
    ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", scriptPath, "-Port", String(PORT)],
    {
      cwd: DECISION_HUB_ROOT,
      env: process.env,
      windowsHide: true
    }
  );

  hubProcess.stdout.on("data", (chunk) => appendLog(`[hub] ${chunk.toString().trim()}`));
  hubProcess.stderr.on("data", (chunk) => appendLog(`[hub:error] ${chunk.toString().trim()}`));
  hubProcess.on("exit", (code) => {
    appendLog(`Decision Hub exited with code ${code}`);
    hubProcess = null;
    if (!isQuitting && restartAttempts < 1) {
      restartAttempts += 1;
      startDecisionHub();
      if (mainWindow) mainWindow.webContents.send("service-message", "Decision Hub restarted.");
    } else if (!isQuitting) {
      dialog.showErrorBox("Decision Hub stopped", "The local service stopped. Use the tray menu to restart it.");
    }
  });
}

async function createWindow() {
  startDecisionHub();
  await waitForHub();

  mainWindow = new BrowserWindow({
    width: 1280,
    height: 820,
    minWidth: 1024,
    minHeight: 680,
    title: "International Trade Cloud OS",
    autoHideMenuBar: true,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false
    }
  });

  await mainWindow.loadURL(HUB_URL);
  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

function restartHub() {
  restartAttempts = 0;
  if (hubProcess) hubProcess.kill();
  setTimeout(() => {
    startDecisionHub();
    waitForHub()
      .then(() => {
        if (mainWindow) mainWindow.loadURL(HUB_URL);
      })
      .catch((error) => dialog.showErrorBox("Restart failed", error.message));
  }, 700);
}

function createTray() {
  try {
    tray = new Tray(ICON_PATH);
    tray.setToolTip("International Trade Cloud OS");
    tray.setContextMenu(Menu.buildFromTemplate([
      { label: "打开系统", click: () => (mainWindow ? mainWindow.show() : createWindow()) },
      { label: "重启本地服务", click: restartHub },
      { label: "查看服务日志", click: () => shell.openPath(LOG_PATH) },
      { type: "separator" },
      { label: "退出", click: () => { isQuitting = true; app.quit(); } }
    ]));
  } catch (error) {
    appendLog(`[tray:error] ${error.stack || error.message}`);
  }
}

app.whenReady().then(async () => {
  appendLog(`App ready. packaged=${app.isPackaged} resources=${process.resourcesPath || ""}`);
  app.setLoginItemSettings({
    openAtLogin: process.env.CLOUD_OS_OPEN_AT_LOGIN === "1"
  });
  createTray();
  try {
    await createWindow();
  } catch (error) {
    appendLog(`[desktop:error] ${error.stack || error.message}`);
    dialog.showErrorBox("Cloud OS start failed", error.message);
  }
});

app.on("window-all-closed", (event) => {
  event.preventDefault();
  if (mainWindow) mainWindow.hide();
});

app.on("before-quit", () => {
  isQuitting = true;
  if (hubProcess) hubProcess.kill();
});
