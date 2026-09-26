# HR Analytica

HR Analytica 是一个面向人力资源与财务交叉场景的数据分析与报告工具。

## 最终发布形态

- 正式 Release 提供：完整功能的 Streamlit 单文件 exe
- 源码保留：FastAPI 后端、Streamlit 前端、Electron 桌面探索版
- Electron 版当前仅完成薪酬分析，作为架构探索保留，不作为最终发布形态

## 访问码

默认访问码：

```text
HR2026
```

可以通过环境变量覆盖：

```powershell
$env:HR_ANALYTICA_ACCESS_CODE="你的访问码"
```

## 项目结构

```text
backend/
  analysis_engine.py       # 完整数据分析引擎
  salary_core.py           # 纯 pandas 共享薪酬核心
  database.py              # SQLite 数据层
  api.py                   # FastAPI 接口
  main.py                  # FastAPI 应用对象
  server_entry.py          # 桌面 sidecar 入口
frontend/
  app.py                   # Streamlit 前端入口
  api_client.py            # FastAPI HTTP 客户端
desktop/
  main.js                  # Electron 主进程
  preload.js               # 受限 IPC 桥
  renderer/                # Electron 桌面界面
app.py                     # 完整 Streamlit 入口
auth.py                    # 访问码登录
launcher.py                # Streamlit exe 启动器
tests/
  test_analysis_engine.py  # 核心分析测试
  test_backend_api.py      # FastAPI 接口测试
```

## 运行源码

### 后端

```powershell
python -m uvicorn backend.main:app --reload --port 8000
```

### Streamlit 前端

```powershell
python -m streamlit run frontend/app.py
```

### 完整 Streamlit 应用

```powershell
python -m streamlit run app.py
```

### Electron 桌面探索版

```powershell
cd desktop
npm install
npm start
```

## 测试

```powershell
python -m pytest -q
```

当前测试结果：

```text
38 passed
```

## 构建

### Streamlit 单文件 exe

```powershell
python -m PyInstaller --clean --noconfirm HR_Analysis_Assistant.spec
```

输出：

```text
dist/HR_Analysis_Assistant.exe
```

### FastAPI 轻量 sidecar

```powershell
python -m PyInstaller --clean --noconfirm HR_Analytica_Backend.spec
```

输出：

```text
dist/HR_Analytica_Backend/HR_Analytica_Backend.exe
```

### Electron 安装包

```powershell
cd desktop
npm run dist
```

输出：

```text
desktop-dist/HR-Analytica-Setup-0.2.0-x64.exe
```

## API

| 接口 | 说明 |
| :--- | :--- |
| `GET /api/health` | 健康检查 |
| `POST /api/analyze_salary` | 上传薪酬 CSV/Excel，返回统计、渗透率和诊断建议 |
| `GET /api/history` | 读取历史分析记录 |

## 数据位置

桌面运行数据保存在：

```text
%APPDATA%/HR Analytica
```

其中包括 SQLite 数据库、桌面日志、API 日志和错误日志。