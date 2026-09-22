const params = new URLSearchParams(window.location.search);
const apiPort = params.get("apiPort") || "8000";
const apiBase = `http://127.0.0.1:${apiPort}`;

const fileInput = document.getElementById("fileInput");
const dropZone = document.getElementById("dropZone");
const fileName = document.getElementById("fileName");
const analyzeButton = document.getElementById("analyzeButton");
const historyButton = document.getElementById("historyButton");
const status = document.getElementById("status");
const emptyState = document.getElementById("emptyState");
const resultContent = document.getElementById("resultContent");
const metrics = document.getElementById("metrics");
const statsTable = document.getElementById("statsTable");
const penetrationTable = document.getElementById("penetrationTable");
const summary = document.getElementById("summary");
const historyId = document.getElementById("historyId");
const historyDialog = document.getElementById("historyDialog");
const historyContent = document.getElementById("historyContent");
const closeHistoryButton = document.getElementById("closeHistoryButton");

document.getElementById("apiBase").textContent = apiBase;

function setStatus(message, kind = "idle") {
  status.textContent = message;
  status.className = `status status-${kind}`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function renderTable(container, rows) {
  if (!Array.isArray(rows) || rows.length === 0) {
    container.innerHTML = '<div class="empty-state">暂无数据</div>';
    return;
  }
  const columns = Object.keys(rows[0]);
  const head = columns.map((column) => `<th>${escapeHtml(column)}</th>`).join("");
  const body = rows
    .map(
      (row) =>
        `<tr>${columns
          .map((column) => `<td>${escapeHtml(row[column])}</td>`)
          .join("")}</tr>`
    )
    .join("");
  container.innerHTML = `<table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
}

function renderMetrics(result) {
  const items = [
    ["数据行数", result.rows],
    ["总体平均薪资", Number(result.overall_mean || 0).toLocaleString()],
    ["分组数量", (result.group_stats || []).length],
  ];
  metrics.innerHTML = items
    .map(
      ([label, value]) =>
        `<div class="metric"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`
    )
    .join("");
}

function renderResult(result) {
  emptyState.classList.add("hidden");
  resultContent.classList.remove("hidden");
  historyId.textContent = result.history_id ? `历史 ID: ${result.history_id}` : "";
  historyId.classList.toggle("hidden", !result.history_id);
  renderMetrics(result);
  renderTable(statsTable, result.group_stats || []);
  renderTable(penetrationTable, result.penetration || []);
  summary.textContent = [result.summary, result.advice].filter(Boolean).join("\n\n");
}

function selectFile(file) {
  if (!file) {
    fileName.textContent = "尚未选择文件";
    analyzeButton.disabled = true;
    return;
  }
  fileName.textContent = `${file.name} · ${(file.size / 1024).toFixed(1)} KB`;
  analyzeButton.disabled = false;
}

fileInput.addEventListener("change", () => selectFile(fileInput.files[0]));

["dragenter", "dragover"].forEach((eventName) => {
  dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropZone.classList.add("dragging");
  });
});

["dragleave", "drop"].forEach((eventName) => {
  dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropZone.classList.remove("dragging");
  });
});

dropZone.addEventListener("drop", (event) => {
  const file = event.dataTransfer.files[0];
  if (file) {
    const transfer = new DataTransfer();
    transfer.items.add(file);
    fileInput.files = transfer.files;
    selectFile(file);
  }
});

analyzeButton.addEventListener("click", async () => {
  const file = fileInput.files[0];
  if (!file) {
    return;
  }
  analyzeButton.disabled = true;
  setStatus("正在分析...", "idle");
  const form = new FormData();
  form.append("file", file);

  try {
    const response = await fetch(`${apiBase}/api/analyze_salary`, {
      method: "POST",
      body: form,
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || `HTTP ${response.status}`);
    }
    renderResult(payload);
    setStatus("分析完成", "ok");
  } catch (error) {
    setStatus(`分析失败：${error.message}`, "error");
  } finally {
    analyzeButton.disabled = false;
  }
});

historyButton.addEventListener("click", async () => {
  setStatus("正在读取历史记录...", "idle");
  try {
    const response = await fetch(`${apiBase}/api/history?limit=20`);
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || `HTTP ${response.status}`);
    }
    renderTable(historyContent, payload);
    historyDialog.showModal();
    setStatus("历史记录已加载", "ok");
  } catch (error) {
    setStatus(`历史读取失败：${error.message}`, "error");
  }
});

closeHistoryButton.addEventListener("click", () => historyDialog.close());

fetch(`${apiBase}/api/health`)
  .then((response) => {
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    return response.json();
  })
  .then(() => setStatus("本地服务已连接", "ok"))
  .catch((error) => setStatus(`本地服务未连接：${error.message}`, "error"));
