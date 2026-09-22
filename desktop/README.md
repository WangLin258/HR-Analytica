# HR Analytica Desktop Skeleton

这是桌面版的第一阶段骨架，用于验证：

1. Electron 主进程启动本地 Python 后端。
2. 后端在随机可用端口提供 FastAPI 接口。
3. 桌面渲染页面直接上传薪酬文件并调用 `/api/analyze_salary`。
4. 分析结果写入 SQLite，并可通过 `/api/history` 查询。

## 开发运行

在项目根目录启动后端：

```powershell
python -m backend.server_entry
```

另开终端安装并启动 Electron：

```powershell
cd desktop
npm install
npm start
```

`desktop/main.js` 会自动选择空闲端口并启动后端，开发阶段默认调用当前环境中的 Python。打包阶段再把 `backend/` 打成独立 sidecar exe，放到 Electron 的 `resources/backend/` 目录。
