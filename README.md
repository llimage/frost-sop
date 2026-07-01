# S-O-P V1.0-MVP

> **版本**: V1.0-MVP
> **日期**: 2026-06-07
> **状态**: 编码阶段 Phase 1-4
> **技术栈**: NiceGUI + Ollama(qwen2.5:3b) + SQLite + ChromaDB

---

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 确保Ollama运行且模型已下载
ollama list  # 应显示 qwen2.5:3b 和 nomic-embed-text

# 3. 启动系统
python main.py

# 4. 浏览器自动打开 http://localhost:8080
```

## 项目结构

```
Solo-Ops-Platform/
├── main.py                 # 系统启动入口
├── requirements.txt        # 依赖
├── core/                   # 核心服务层
│   ├── config.py          # SecureConfig (Fernet加密)
│   ├── database.py        # Database (SQLite)
│   ├── memory.py          # MemoryStore (ChromaDB)
│   ├── llm_client.py      # LLMClient (Ollama+云端)
│   ├── cost_tracker.py    # CostTracker (成本追踪)
│   ├── permission.py      # PermissionChecker (P0-P4)
│   ├── toolkit.py         # ToolKit (工具框架+沙箱)
│   ├── scheduler.py       # Scheduler (调度器中枢)
│   └── sop_engine.py      # SOPEngine (SOP引擎)
├── agents/                 # Agent层
│   ├── base.py            # BaseAgent (抽象基类)
│   ├── main_agent.py      # MainAgent (意图解析+调度)
│   ├── audit_agent.py     # AuditAgent (审查+监督)
│   └── dev_agent.py       # DevAgent (代码+工具)
├── frontend/               # 前端层 (NiceGUI)
│   ├── app.py             # NiceGUI主入口
│   ├── dashboard.py       # 仪表盘页面
│   ├── settings.py        # 设置页面
│   ├── components.py      # 共享组件
│   └── styles.py          # 设计系统常量
├── sops/                   # SOP模板
│   ├── DEV-001.yaml       # 新功能开发
│   ├── DEV-002.yaml       # Bug修复
│   └── STR-002.yaml       # 周期性回顾
├── data/                   # 数据目录 (自动创建)
│   ├── solo_ops.db        # SQLite数据库
│   ├── chromadb/           # ChromaDB向量库
│   ├── backups/            # 自动备份
│   └── .secret_key         # Fernet密钥
├── logs/                   # 日志目录
└── output/                 # 输出目录
```

## 设计文档

见 `docs/waterfall/02-系统设计/` 目录：
- `02.1-系统架构设计.md`
- `02.2-数据库设计.md`
- `02.3-接口设计.md`
- `02.4-UIUX设计.md`
- `02.5-安全设计.md`

## 开发计划

见 `docs/waterfall/03-编码阶段/03.1-开发计划.md`

## 实验结果

见 `experiments/RESULTS.md`

---

*本地优先 · 数据主权 · AI赋能*
