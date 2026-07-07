# FROST-SOP 部署指南（Windows）

> 版本：V7.1
> 适用：廖亮的一人公司环境
> 预计首次部署时间：30 分钟

---

## 前置条件

| 依赖 | 版本要求 | 检查命令 |
|------|---------|---------|
| Python | 3.11+ | `python --version` |
| Node.js | 18+ | `node --version` |
| Git | 任意 | `git --version` |

**如果未安装：**
- Python：https://www.python.org/downloads/（安装时勾选"Add to PATH"）
- Node.js：https://nodejs.org/（推荐 LTS 版本）

---

## 1. 克隆代码

```powershell
cd D:\my_ai\Solo-Ops-Platform
git clone https://github.com/llimage/frost-sop.git
# 或：git clone https://gitee.com/liao_liang_7514/frost-sop.git
cd frost-sop
```

---

## 2. 安装依赖

### Python 依赖

```powershell
pip install -r requirements.txt
```

**常见错误：**
- 如果 `llama-cpp-python` 安装失败 → 不影响，这是可选的本地 LLM 支持
- 如果 `chromadb` 安装失败 → 不影响，系统会自动降级到内存模式

### 前端依赖

```powershell
cd frontend
npm install
cd ..
```

---

## 3. 配置 API Key

复制示例配置：

```powershell
copy .env.example .env
```

编辑 `.env` 文件，填入你的 DeepSeek API Key：

```
DEEPSEEK_API_KEY=sk-你的密钥
```

**获取密钥：** https://platform.deepseek.com/

---

## 4. 启动系统

### 方式一：双击启动（推荐）

```
双击 start.bat
```

等待 10 秒，自动打开：
- 前端：http://localhost:3000
- API：http://localhost:8000

### 方式二：手动启动

**终端 1（API）：**
```powershell
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

**终端 2（前端）：**
```powershell
cd frontend
npm run dev
```

---

## 5. 验证启动成功

打开浏览器访问：

1. **前端页面**：http://localhost:3000 → 应看到任务列表和成本面板
2. **API 文档**：http://localhost:8000/docs → 应看到 FastAPI 自动生成的接口文档
3. **健康检查**：http://localhost:8000/api/health → 应返回 `{"status":"ok"}`

---

## 6. 运行验收（必须）

首次部署后，执行验收流程确认系统可用：

```powershell
# 运行冒烟测试
pytest tests/smoke/ -m smoke -v

# 执行一个真实任务（如长护险竞品调研）
# 在前端页面创建任务，SOP 选择 OPS-007
```

详细验收流程参见：`sops/templates/OPS-ACCEPT-001.yaml`

---

## 7. 关闭系统

**方式一：** 关闭 start.bat 弹出的命令窗口

**方式二：** 手动终止
```powershell
taskkill /FI "WINDOWTITLE eq FROST-SOP*" /T /F
```

---

## 常见问题

| 问题 | 解决 |
|------|------|
| `ModuleNotFoundError` | 运行 `pip install -r requirements.txt` |
| `npm ERR!` | 删除 `frontend/node_modules`，重新 `npm install` |
| API 返回 500 | 检查 `.env` 中的 `DEEPSEEK_API_KEY` 是否正确 |
| 前端白屏 | 检查 API 是否已启动（http://localhost:8000/api/health） |
| 数据库被锁 | 关闭所有终端，重新启动 |

---

## 数据备份

SQLite 数据库位于 `data/frost_sop.db`。**建议每周复制一份备份：**

```powershell
copy data\frost_sop.db data\frost_sop_backup_20260617.db
```

---

## 升级系统

```powershell
git pull github master
# 或：git pull origin master
pip install -r requirements.txt
cd frontend && npm install && cd ..
```

---

> **首次部署完成后，请执行 OPS-ACCEPT-001 验收流程，确认系统可用。**
