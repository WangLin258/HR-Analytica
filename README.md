# HR Analytica

HR Analytica 是一个面向人力资源与财务交叉场景的数据分析与报告工具。

当前项目同时保留三种运行形态：

1. 完整 Streamlit 应用
2. FastAPI 分析服务
3. Electron 桌面应用

## 项目结构

```text
backend/
  analysis_engine.py       # 数据清洗、薪酬分析、招聘分析、报告导出
  config.py                # 后端路径与运行配置
  database.py              # SQLite 数据访问层
  api.py                   # FastAPI 接口
  main.py                  # FastAPI 应用对象
  server_entry.py          # 桌面 sidecar 启动入口
frontend/
  app.py                   # Streamlit 前端入口
  api_client.py            # FastAPI HTTP 客户端
desktop/
  main.js                  # Electron 主进程
  preload.js               # 受限 IPC 桥
  renderer/                # 桌面界面
app.py                     # 完整 Streamlit 入口
HR_Analytica_Backend.spec  # 后端 sidecar PyInstaller 配置
HR_Analysis_Assistant.spec # 单进程 Streamlit exe 配置
launcher.py                # Streamlit 桌面启动器
```

## 开发运行

### 后端服务

```powershell
python -m uvicorn backend.main:app --reload --port 8000
```

### Streamlit 前端

```powershell
python -m streamlit run frontend/app.py
```

### Electron 桌面应用

先启动后端，或在桌面开发模式中由 Electron 自动拉起后端：

```powershell
cd desktop
npm install
npm start
```

## 第一阶段接口

| 接口 | 说明 |
| :--- | :--- |
| `GET /api/health` | 健康检查 |
| `POST /api/analyze_salary` | 上传薪酬 CSV/Excel，返回统计、渗透率和诊断建议 |
| `GET /api/history` | 读取历史分析记录 |

## 构建 Windows 后端 sidecar

```powershell
python -m PyInstaller --clean --noconfirm HR_Analytica_Backend.spec
```

输出：

```text
dist/HR_Analytica_Backend/HR_Analytica_Backend.exe
```

## 构建 Windows 桌面安装包

```powershell
cd desktop
npm run dist
```

输出：

```text
desktop-dist/HR-Analytica-Setup-0.1.0-x64.exe
```

## 桌面版运行数据

桌面应用运行数据保存在：

```text
%APPDATA%\HR Analytica
```

其中包括 SQLite 数据库、桌面日志、后端日志和错误日志。