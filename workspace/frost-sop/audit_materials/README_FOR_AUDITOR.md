# README_FOR_AUDITOR — 审计师使用说明

欢迎，审计师！

本材料包已为您准备好 S-O-P (FROST-SOP) 项目的全部关键信息。以下是推荐阅读顺序：

---

## 📖 阅读路线

```
1. AUDIT_REQUEST.md         ← 从这里开始！了解审计目标和要求
       │
       ▼
2. PROJECT_OVERVIEW.md      ← 了解项目定位、规模、开发历史
       │
       ▼
3. ARCHITECTURE_DIAGRAM.md  ← 理解系统架构、数据流、模块依赖
       │
       ▼
4. CORE_MODULES_SUMMARY.md  ← 深入每个核心模块的代码结构
       │
       ▼
5. DEPENDENCIES.md          ← 了解技术栈和外部依赖
       │
       ▼
6. TEST_COVERAGE.md         ← 查看测试覆盖现状
       │
       ▼
7. KNOWN_ISSUES.md          ← 了解已知问题和风险
       │
       ▼
8. 输出审计报告              ← 按 AUDIT_REQUEST.md 要求输出
```

---

## 🔍 如果需要完整代码

本材料包提供了核心模块的代码摘要（关键函数列表和概要描述）。

如需任何文件的**完整源代码**，请告知文件路径。以下为最可能需要完整代码的文件：

| 文件 | 行数 | 审计价值 |
|------|------|----------|
| `core/db.py` | 936 | 所有 SQL 查询和表结构 |
| `core/store.py` | 308 | 三级存储体系完整逻辑 |
| `core/agent.py` | 245 | Agent 核心类 |
| `skills/orchestration.py` | 357 | SOP 编排逻辑 |
| `skills/llm.py` | 284 | LLM 调用和 mock 路由 |
| `skills/assemble.py` | 283 | 孙辈 Agent 组装逻辑 |
| `api/main.py` | 523 | FastAPI 13 个端点完整实现 |
| `api/models.py` | 153 | Pydantic 模型定义 |
| `frontend/src/app/page.tsx` | 231 | 驾驶舱首页 |
| `frontend/src/lib/api.ts` | 78 | 前端 API 调用层 |

---

## 📁 材料包结构

```
audit_materials/
├── README_FOR_AUDITOR.md       ← 本文件
├── AUDIT_REQUEST.md            ← 审计目标和输出要求
├── PROJECT_OVERVIEW.md         ← 项目概览
├── ARCHITECTURE_DIAGRAM.md     ← 架构图 + 数据流
├── CORE_MODULES_SUMMARY.md     ← 核心模块代码摘要
├── DEPENDENCIES.md             ← 依赖清单
├── TEST_COVERAGE.md            ← 测试覆盖报告
└── KNOWN_ISSUES.md             ← 已知问题清单
```

---

## ⚡ 快速了解项目

如果您只有 5 分钟，请阅读：

1. `AUDIT_REQUEST.md` 中的"审计维度"和"审计输出要求"
2. `PROJECT_OVERVIEW.md` 中的"技术架构总览"和"核心模块列表"
3. `KNOWN_ISSUES.md` 中的汇总表（12 个已知问题）

如果您有 30 分钟，请按阅读路线从头到尾阅读。

---

## 💡 审计提示

- 本项目设计哲学：**FROST 分形架构** — 所有 Agent 行为由 SOP 模板驱动，不硬编码
- 项目处于 **开发末期**，功能已完工，正在准备上线前的质量审计
- 测试通过率 88.7%，2 个 P0 已知问题待修复
- 前后端完全分离：FastAPI + Next.js（Streamlit 为遗留工作台）

---

*祝审计愉快！*
