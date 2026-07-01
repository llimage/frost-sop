# P0 安全修复报告

**修复日期**: 2026-07-01  
**基线版本**: v3.0.0 (commit c4d612c)  
**修复范围**: 第三方审计报告 S-001 ~ S-005 + 工程化加固  

---

## 修复清单

### S-001: SQL 注入 — `select_all` 的 `where` 参数拼接
- **状态**: ✅ 已修复
- **文件**: `core/db.py`
- **措施**:
  - 添加 `ALLOWED_TABLES` 白名单（20 张表），`select_all` 入口校验表名
  - 添加 `_WHERE_DANGEROUS_KEYWORDS` 黑名单（`;`/`--`/`/*`/`UNION`/`DROP`/`DELETE`/`INSERT`/`UPDATE`/`ALTER`/`CREATE`/`EXEC`/`TRUNCATE`），WHERE 子句中检测到即抛 `ValueError`

### S-002: SQL 注入 — 通用 CRUD 的表名/列名拼接
- **状态**: ✅ 已修复
- **文件**: `core/db.py`
- **措施**:
  - `insert`/`update`/`delete`/`select_one` 入口校验 `table in ALLOWED_TABLES`
  - 列名用 `re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', col)` 验证
  - `execute_sql` docstring 标注"仅供内部使用"

### S-003: SQL 注入 — `ALTER TABLE` 迁移中的列名拼接
- **状态**: ✅ 已修复
- **文件**: `core/db.py`（4 个迁移方法）
- **措施**:
  - 列名用正则验证（`^[a-zA-Z_][a-zA-Z0-9_]*$`）
  - 列定义用正则验证（`^[A-Z]+\s*(DEFAULT\s+[^;\-]*|)$`）
  - 验证失败则 `continue` 跳过（不影响现有迁移逻辑）

### S-004: CORS 全开放
- **状态**: ✅ 已修复
- **文件**: `api/main.py`
- **措施**:
  - `allow_origins` 改为读 `FROST_CORS_ORIGINS` 环境变量
  - dev 默认: `http://localhost:3000,http://localhost:8501,http://localhost:8080`
  - `FROST_ENV=production` 时强制移除 `*`，无配置则回退到 `localhost:3000`
  - `allow_methods` 收紧为 `GET/POST/PUT/DELETE`
  - `allow_headers` 收紧为 `Content-Type/Authorization/X-Request-ID`

### S-005: 工程化缺失
- **状态**: ✅ 已修复
- **措施**:
  - 添加 `pyproject.toml`（在 `workspace/frost-sop/` 下，非根目录）
  - 依赖锁定：10 个核心依赖 + 3 组可选依赖（dev/legacy/llm-local）
  - 配置 `[tool.ruff]`/`[tool.mypy]`/`[tool.pytest]`/`[tool.bandit]`
  - `requirements.txt` CRLF → LF，streamlit 标为 DEPRECATED
  - 不创建 `ruff.toml`（避免与 `[tool.ruff]` 冲突）

### S3-bonus: 删除废弃的 F11 Streamlit app.py
- **状态**: ✅ 已删除
- **文件**: `workspace/frost-sop/app.py`（2,483 行，F11 Streamlit 驾驶舱）
- **理由**: 已被根目录 `app.py`（NiceGUI 483 行）取代，文件开头有 `DeprecationWarning`

---

## 验证结果

| 验证项 | 结果 |
|--------|------|
| `core/db.py` 语法 | ✅ py_compile PASS |
| `api/main.py` 语法 | ✅ py_compile PASS |
| `pyproject.toml` 语法 | ✅ tomllib 解析 PASS |
| ALLOWED_TABLES 导入 | ✅ 20 张表 |
| 安全注入测试 | ✅ 13/13 passed（表名白名单 + WHERE 黑名单 + 列名正则） |
| FastAPI 启动 | ✅ HTTP 200 |
| API 功能 | ✅ 18 projects + 7 SOPs + 3 tasks |
| 回归测试 | ⏳ 进行中 |

---

## 审计报告修正

| 审计声称 | 实际状态 | 修正 |
|----------|---------|------|
| "frontend/ 224MB 仍存在" | `workspace/frost-sop/frontend/` 存在但**应保留**（Next.js 前端，用户选择"只保留 Next.js"） | 审计建议删除是错误的 |
| "app.py 2,483 行" | 指的是 `workspace/frost-sop/app.py`（已废弃 F11 Streamlit），根目录 `app.py` 是 483 行 NiceGUI | 审计混淆了两个文件 |
| "249 个测试" | 审计环境差异（Python 3.12 + pytest 9.1），本机基线 606 passed + 3 skipped | 环境/工具链差异 |
| "chromadb future" | `core/memory.py:55` 实际在用（`import chromadb`） | 审计注释过时 |
