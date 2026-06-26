# DEPENDENCIES — 依赖清单

## Python 依赖 (requirements.txt)

```
pyyaml>=6.0           # YAML SOP 模板解析
openai>=1.0.0         # OpenAI/DeepSeek API 调用
python-dotenv>=1.0.0  # .env 环境变量加载
streamlit>=1.28.0     # Streamlit 工作台 UI
requests>=2.31.0      # HTTP 请求
win10toast>=0.9       # Windows 系统通知
plyer>=2.1.0          # 跨平台桌面通知
```

### 隐式 Python 依赖（未在 requirements.txt 中声明，但代码中引用）

| 包 | 用途 | 文件 |
|----|------|------|
| `chromadb` | 向量语义检索 | core/memory.py |
| `pytest` | 测试框架 | tests/ 全量 |

> **审计提示**: chromadb 和 pytest 未在 requirements.txt 中声明。chromadb 是运行时依赖（memory.py 中 import），缺失会导致知识库检索不可用。pytest 是开发依赖。

---

## Node.js 前端依赖 (frontend/package.json)

```json
{
  "dependencies": {
    "@base-ui/react": "^1.6.0",         // shadcn v4 基座
    "@tanstack/react-query": "^5.101.1", // 服务端状态管理
    "axios": "^1.18.1",                  // HTTP 客户端
    "class-variance-authority": "^0.7.1", // CVA 变体工具
    "clsx": "^2.1.1",                    // 类名合并
    "cmdk": "^1.1.1",                    // Command 菜单
    "date-fns": "^4.4.0",                // 日期处理
    "lucide-react": "^1.21.0",           // 图标库
    "next": "16.2.9",                    // Next.js 框架
    "react": "19.2.4",                   // React
    "react-dom": "19.2.4",               // React DOM
    "react-day-picker": "^10.0.1",       // 日期选择器
    "recharts": "^3.9.0",                // 图表库
    "tailwind-merge": "^3.6.0",          // Tailwind 类名合并
    "tw-animate-css": "^1.4.0",          // Tailwind 动画
    "zustand": "^5.0.14"                 // 客户端状态管理
  },
  "devDependencies": {
    "@tailwindcss/postcss": "^4",        // Tailwind CSS PostCSS 插件
    "@types/node": "^20",                // Node.js 类型
    "@types/react": "^19",               // React 类型
    "@types/react-dom": "^19",           // React DOM 类型
    "eslint": "^9",                      // ESLint
    "eslint-config-next": "16.2.9",      // Next.js ESLint 配置
    "tailwindcss": "^4",                 // Tailwind CSS
    "typescript": "^5"                   // TypeScript
  }
}
```

---

## 数据库依赖

| 组件 | 版本/类型 | 存储位置 | 用途 |
|------|-----------|----------|------|
| **SQLite** | 内置 (Python sqlite3) | `data/frost_sop.db` | 主持久化 (17 张表) |
| **ChromaDB** | pip 安装 | `data/chromadb/` | 向量语义检索 (知识库) |

### SQLite 表清单 (17 张)

| 表名 | 用途 | 关键字段数 |
|------|------|-----------|
| tasks | 任务主表 | 9 |
| task_stages | 任务阶段记录 | 8 |
| sop_executions | SOP 执行记录 | 8 |
| sop_templates | SOP 模板存储 | 8 |
| agents | Agent 注册表 | 7 |
| agent_status | Agent 在线状态 | 7 |
| cost_log | LLM 费用追踪 | 8 |
| projects | 项目定义 | 11 |
| skills | 技能库 | 12 |
| skill_versions | 技能版本历史 | 7 |
| project_skills | 项目-技能关联 | 4 |
| decision_points | 决策点记录 | 15 |
| audit_log | 审计日志 | 5 |
| energy_log | 能量记录 | 8 |
| schedule | 日程管理 | 13 |
| daily_reviews | 日终回顾 | 8 |
| knowledge / knowledge_tags | 知识库 | 7+2 |
| config / config_snapshots | 系统配置 | 8+5 |
| kv_store | 通用键值存储 | 4 |
| tool_calls | 工具调用日志 | 8 |

---

## 外部 API 依赖

| API 服务 | 用途 | 配置方式 |
|----------|------|----------|
| **DeepSeek API** (deepseek-chat) | LLM 调用 | 环境变量 `DEEPSEEK_API_KEY` (.env) |
| **OpenAI API** | 备用 LLM | 环境变量 `OPENAI_API_KEY` (.env) |

### .env 配置模板

```env
DEEPSEEK_API_KEY=sk-xxxxx
OPENAI_API_KEY=sk-xxxxx
FROST_TESTING=1              # 测试模式（跳过真实 LLM 调用）
NEXT_PUBLIC_API_URL=http://localhost:8000/api
```

---

## 运行时要求

| 组件 | 最低版本 | 实际使用 |
|------|----------|---------|
| Python | 3.11+ | 3.13.12 |
| Node.js | 20+ | 22.22.2 |
| npm/pnpm | — | npm (随 Node 安装) |
| SQLite | 3.x (内置于 Python) | 3.x |
| ChromaDB | — | pip 独立安装 |
