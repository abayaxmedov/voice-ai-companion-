const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("companion", {
  ensureBackend: () => ipcRenderer.invoke("backend:ensure"),
  orchestratorUrl: "http://127.0.0.1:8765",
});
