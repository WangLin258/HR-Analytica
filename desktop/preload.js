const { contextBridge } = require("electron");

contextBridge.exposeInMainWorld("hrAnalyticaDesktop", {
  platform: process.platform,
});
