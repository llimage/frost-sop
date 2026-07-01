# FROST-SOP v5.0.0 基线

**创建日期**: 2026-07-02
**Git Tag**: v5.0.0
**Git Commit**: f1de2feb7ad1867acf9d887e44294dcfacc73997
**执行者**: WorkBuddy

## 基线内容

| 组件 | 状态 | 说明 |
|------|------|------|
| 核心框架 | 稳定 | Store/Skill/Agent/SOP/EventBus 可用 |
| 安全修复 | 已完成 | SQL注入白名单、CORS限制、pyproject.toml |
| 测试工具链 | 已配置 | pytest-xdist、Hypothesis、benchmark、CI/CD |
| 文件系统 | 已清理 | 空壳删除、审计报告归档、缓存清理 |
| 武器库 | 已启用 | DecisionFlow 集成、健康评分系统就绪 |

## 测试基线 (S4-3 最终验证: 2026-07-02 01:20)

| 指标 | 数值 |
|------|------|
| 收集到的测试 | 757 (1 skipped in collection, 不含 test_api_contract.py) |
| 通过 | **全部通过 (pytest exit code = 0)** |
| 单独运行验证 | ✅ 所有 flaky 测试单独运行全通过 |
| 已知跳过 | ~8 (V3 订阅者泄漏、V4 P1 acceptance 等) |
| 已知 flaky (不影响 exit code) | test_cost_tracker_budget_check (自定义状态打印), test_chromadb_add_and_search (MemoryStore 接口), F9 系列 (DB 单例污染) |
| Python 版本 | 3.13.12 (需 `-s` 参数) |
| 运行命令 | `FROST_TESTING=1 python -X utf8 -m pytest tests/ --ignore=tests/test_api_contract.py --tb=no -s` |
| 备注 | Python 3.13 + pytest `-s` 参数导致标准汇总行不显示，以 exit code 0 为准 |

## 测试工具链 (45-49)

| # | 工具 | 状态 | 说明 |
|---|------|------|------|
| 45 | 变异测试 (cosmic-ray) | 已配置 | core/monitor.py, 52.44% kill rate |
| 46 | 故障注入 | 16 tests | 15 passed, 1 flaky (并发读) |
| 47 | API 契约 (schemathesis) | 31 tests | 30 passed + 1 hang (logs endpoint) |
| 48 | 性能 SLO (pytest-benchmark) | 11 tests | 全部达标 |
| 49 | CI + 审计 | 已完成 | AUDIT_REPORT_V3.1.md |

## 代码覆盖率

| 指标 | 数值 |
|------|------|
| 覆盖率 | ~58.64% |

## 已知限制

1. pytest-xdist 并行测试因 SQLite 锁冲突不可行（需串行运行）
2. CI/CD 中 ruff/mypy 版本号需修正（ruff==0.11.0, mypy==1.15.0）
3. `record_usage()` / `merge_from()` 已修复但未验证实际运行
4. 负载测试（Locust）和变异测试（Cosmic-ray）已配置但未全量运行
5. F9 相关测试在全量运行时因 DB 单例污染而 flaky（单独运行全通过）
6. `/api/logs` 端点测试导致进程崩溃（DB 连接生命周期问题）
7. Python 3.13 + pytest 需 `-s` 参数（capture 模块兼容性问题）

## 审计就绪

本基线已准备就绪，可供第三方审计。审计报告见：
- 项目根目录: `AUDIT_REPORT_V3.1.md`
- 归档目录: `workspace/frost-sop/archive/audits/`

## 目录结构

```
Solo-Ops-Platform/                     # Git 仓库根目录
├── app.py                             # NiceGUI 驾驶舱
├── start_nicegui.py                   # NiceGUI 启动脚本
├── start_all.bat / stop_all.bat       # 一键启停
├── README.md
├── .gitignore                         # v5.0.0 更新
├── AUDIT_REPORT_V3.1.md               # 第三方审计报告
└── workspace/frost-sop/               # FROST-SOP 主代码目录
    ├── agents/          # 三代 Agent (elder/parent/孙辈组装)
    ├── api/             # FastAPI 服务
    ├── core/            # 核心框架 (Store, SOP, EventBus, DB, etc.)
    ├── skills/          # 技能库
    ├── renderers/       # 渲染器
    ├── stores/          # 数据存储
    ├── sops/            # SOP 模板 (7 个 YAML)
    ├── tests/           # 测试套件 (788 tests)
    ├── docs/            # 文档
    │   └── archive/     # 已归档旧文档（不在 Git 追踪中）
    ├── archive/         # 归档（审计报告等，不在 Git 追踪中）
    │   └── audits/
    ├── data/            # 运行时数据
    ├── logs/            # 日志
    ├── frontend/        # Next.js 前端
    ├── .github/workflows/  # CI/CD
    ├── Makefile         # 构建脚本
    ├── pyproject.toml   # 项目配置
    ├── requirements.txt # 依赖
    ├── main.py          # CLI 入口
    └── BASELINE_v5.0.0.md  # 本文件
```

## 版本历史

| 版本 | 标签 | 日期 | 说明 |
|------|------|------|------|
| v2.0.0 | git tag | 2026-06-26 | EventBus + 事件驱动架构 |
| v3.0.0 | git tag | 2026-06-29 | NiceGUI + V5.0 Panel + Next.js |
| v3.0.0 P0 | commit cfee3f5 | 2026-06-30 | P0 安全修复 |
| **v5.0.0** | **git tag** | **2026-07-02** | **清理基线 + 测试工具链** |
