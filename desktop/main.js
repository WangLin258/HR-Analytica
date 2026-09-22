const { app, BrowserWindow, dialog, shell } = require("electron");
const { spawn, spawnSync } = require("child_process");
const fs = require("fs");
const http = require("http");
const net = require("net");
const path = require("path");

let mainWindow = null;
let backendProcess = null;
let backendPort = null;
let quitting = false;

const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
}

function log(message) {
  try {
    const logPath = path.join(app.getPath("userData"), "desktop.log");
    fs.appendFileSync(logPath, `${new Date().toISOString()} ${message}\n`, "utf8");
  } catch (_) {
    // Logging must never prevent the application from starting.
  }
}

function findFreePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.unref();
    server.on("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const port = server.address().port;
      server.close(() => resolve(port));
    });
  });
}

function findPython() {
  const candidates = [
    process.env.HR_ANALYTICA_PYTHON,
    "C:\\Users\\ASUS\\AppData\\Local\\Python\\pythoncore-3.14-64\\python.exe",
    "python",
    "py",
  ].filter(Boolean);

  for (const candidate of candidates) {
    if (candidate === "python" || candidate === "py") {
      return candidate;
    }
    if (fs.existsSync(candidate)) {
      return candidate;
    }
  }
  return "python";
}

function startBackend(port) {
  const packagedBackend = path.join(
    process.resourcesPath,
    "backend",
    "HR_Analytica_Backend.exe"
  );
  const projectRoot = path.resolve(__dirname, "..");
  const env = {
    ...process.env,
    HR_ANALYTICA_API_PORT: String(port),
    HR_ANALYTICA_HOME: app.getPath("userData"),
    PYTHONUNBUFFERED: "1",
  };

  let command;
  let args;
  let cwd;

  if (fs.existsSync(packagedBackend)) {
    command = packagedBackend;
    args = [];
    cwd = path.dirname(packagedBackend);
  } else {
    command = findPython();
    args = command === "py" ? ["-3", "-m", "backend.server_entry"] : ["-m", "backend.server_entry"];
    cwd = projectRoot;
  }

  log(`Starting backend: ${command} ${args.join(" ")}`);
  backendProcess = spawn(command, args, {
    cwd,
    env,
    windowsHide: true,
    stdio: ["ignore", "pipe", "pipe"],
  });

  backendProcess.stdout.on("data", (data) => log(`[backend] ${data.toString().trim()}`));
  backendProcess.stderr.on("data", (data) => log(`[backend:error] ${data.toString().trim()}`));
  backendProcess.on("error", (error) => log(`Backend process error: ${error.stack || error.message}`));
  backendProcess.on("exit", (code, signal) => {
    log(`Backend exited code=${code} signal=${signal}`);
    backendProcess = null;
    if (!quitting && mainWindow) {
      dialog.showErrorBox("HR Analytica", "本地分析服务已停止，请重新启动应用。");
      mainWindow.close();
    }
  });
}

function stopBackend() {
  if (!backendProcess) {
    return;
  }
  const pid = backendProcess.pid;
  log(`Stopping backend pid=${pid}`);
  try {
    if (process.platform === "win32") {
      spawnSync("taskkill", ["/pid", String(pid), "/T", "/F"], { windowsHide: true });
    } else {
      backendProcess.kill();
    }
  } catch (error) {
    log(`Backend stop failed: ${error.message}`);
  }
  backendProcess = null;
}

function waitForHealth(port, timeoutMs = 120000) {
  const started = Date.now();
  return new Promise((resolve, reject) => {
    const check = () => {
      const request = http.get(
        { host: "127.0.0.1", port, path: "/api/health", timeout: 2000 },
        (response) => {
          response.resume();
          if (response.statusCode === 200) {
            resolve();
            return;
          }
          retry();
        }
      );
      request.on("timeout", () => request.destroy());
      request.on("error", retry);
    };

    const retry = () => {
      if (Date.now() - started >= timeoutMs) {
        reject(new Error("本地分析服务启动超时"));
        return;
      }
      setTimeout(check, 500);
    };

    check();
  });
}

function createWindow(port) {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 860,
    minWidth: 980,
    minHeight: 680,
    title: "HR Analytica",
    backgroundColor: "#f7f8fa",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  mainWindow.webContents.on("did-finish-load", () => log("Renderer loaded"));
  mainWindow.webContents.on("did-fail-load", (_event, code, description) => {
    log(`Renderer load failed code=${code} description=${description}`);
  });
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (/^https?:\/\//i.test(url)) {
      shell.openExternal(url);
    }
    return { action: "deny" };
  });
  mainWindow.webContents.on("will-navigate", (event, url) => {
    if (!url.startsWith("file://")) {
      event.preventDefault();
      if (/^https?:\/\//i.test(url)) {
        shell.openExternal(url);
      }
    }
  });

  mainWindow.loadFile(path.join(__dirname, "renderer", "index.html"), {
    query: { apiPort: String(port) },
  });
  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

async function bootstrap() {
  try {
    backendPort = await findFreePort();
    log(`Selected backend port ${backendPort}`);
    startBackend(backendPort);
    await waitForHealth(backendPort);
    log("Backend health check passed");
    createWindow(backendPort);
  } catch (error) {
    log(`Startup failed: ${error.stack || error.message}`);
    dialog.showErrorBox("HR Analytica 启动失败", error.message);
    stopBackend();
    app.quit();
  }
}

app.whenReady().then(bootstrap);

app.on("second-instance", () => {
  if (mainWindow) {
    if (mainWindow.isMinimized()) {
      mainWindow.restore();
    }
    mainWindow.focus();
  }
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0 && backendPort) {
    createWindow(backendPort);
  }
});

app.on("before-quit", () => {
  quitting = true;
  stopBackend();
});
app.on("window-all-closed", () => {
  stopBackend();
  if (process.platform !== "darwin") {
    app.quit();
  }
});
