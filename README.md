# HR Analytica Phase 1

## 项目结构

```text
backend/
  analysis_engine.py   # 核心薪酬/招聘分析逻辑
  config.py            # 后端配置
  database.py          # SQLite 数据库访问层
  api.py               # FastAPI 路由
  main.py              # FastAPI 启动入口
frontend/
  app.py               # Streamlit 页面（本地直连 / FastAPI 模式）
  api_client.py        # HTTP API 客户端
app.py                 # 旧版完整 Streamlit 入口，保留兼容
```

## 启动方式

后端服务：

```bash
python -m uvicorn backend.main:app --reload --port 8000
```

前端页面：

```bash
python -m streamlit run frontend/app.py
```

旧版完整页面仍可运行：

```bash
python -m streamlit run app.py
```

## 第一阶段接口

| 接口 | 说明 |
| :--- | :--- |
| `GET /api/health` | 健康检查 |
| `POST /api/analyze_salary` | 上传薪酬 CSV/Excel，返回统计、渗透率、诊断建议并写历史 |
| `GET /api/history` | 读取历史分析记录 |

前端侧边栏可选择“本地直连”或“FastAPI 模式”。默认本地直连，方便不启动后端直接使用；切换到 FastAPI 模式后可演示前后端分离。

数据库默认生成在：

```text
backend/hr_data.db
```

日志默认生成在：

```text
backend/api.log
backend/app_errors.log
```
