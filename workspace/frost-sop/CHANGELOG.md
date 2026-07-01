# Changelog

All notable changes to FROST-SOP are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

---

## [3.0.1] - 2026-07-01 (P0 安全 + A 级运行链路)

### 概述
P0 安全审计后的全面加固，以及 FROST 家族资产体系的运行链路修复。本版本使系统从"安全及格但跑不起来"变为"安全达标且核心链路通"。

### Security (P0)
- **SQL注入防护**：`core/db.py` 20表白名单 + 列名正则 `^[a-zA-Z_][a-zA-Z0-9_]*$` + WHERE黑名单（13关键字）
- **CORS安全**：`api/main.py` 从 `["*"]` 改为环境变量 `FROST_CORS_ORIGINS` 驱动
- **废弃代码删除**：`workspace/frost-sop/app.py`（2,483行 Streamlit，已有 NiceGUI 替代）
- **工程硬化**：`pyproject.toml`（ruff/mypy/bandit/pytest 配置）

### Security (S 级修复)
- **S-001 json.loads Schema 验证**：新建 `core/json_safety.py`，6处调用全部加 Pydantic Schema + DoS 防护
- **S-002 input() 阻塞**：`skills/orchestration.py` 新增 `FROST_NON_INTERACTIVE` 环境变量兜底
- **S-003 文件路径验证**：新建 `core/path_safety.py`，6处 `open()` 改为 `safe_open()`
- **S-004 依赖锁定**：13个依赖 `>=` → `==`，构建可复现

### Fixed (A 级运行链路)
- **A-004 merge_from 接入**：`_execute_child()` 中孙辈退出时自动合并 Store 数据到父辈
- **A-005 record_usage 接入**：`_execute_child()` 中每次武器使用后调用 `ArmoryRegistry.record_usage()`
- **A-006 失败复盘**：`SkillExtractor.scan_failed_calls()` → `scan_and_archive_lessons()`，`finalize_task` 中自动触发

### Engineering
- **ruff 0.15.20**：代码检查 + 格式化（2,464 → 202 errors，92% 自动修复）
- **mypy 2.1.0**：类型检查（301 errors，待后续修复）
- **pre-commit 4.6.0**：Git 提交时自动检查
- **.gitignore**：排除 audit_package/ 和临时审计报告

### Test Status
- **全量回归**: 603 passed, 6 skipped, 0 failed

---

## [3.0.0] - 2026-06-29 (Baseline)

### 概述
V3.0 是在 V2.0 事件总线基础上的"治理 + 元数据 + 下一代 UI" 大版本。本版本作为后续 dogfooding 阶段的稳定基线。

### Added

#### V2.0 事件总线（commit v2.0.0）
- `core/event_bus.py` — 事件总线 v2.0.0
  - ancestor / parent / elder 事件订阅
  - v2.0.0 tag 已建立
- V2.1 / V2.2 修补完成

#### V3.0 合并 + P1-1 修复（commit v3.0.0-beta）
- 合并 feature/v2-event-driven → master (0788a5e)
- **P1-1 修复**：3 个文件 `Agent.run()` → `asyncio.to_thread()`
- 四类缺失测试：4 个文件，10 个测试（8 passed + 2 skipped）
- 全量回归：260 passed

#### V4.0 治理 + 驾驶舱
- V4.0 P0-a: 数据采集终端 + 技能图执行引擎
- V4.0 P0-b: 军师分析小组 + 斥候持续狩猎
- V4.0 P1: 驾驶舱动态面板 + 传承系统激活 + 免疫系统 P1/P2
- V4.0 P2: 治理系统数据驱动修订
- V4.0 P2 修复: `apply_revision` 参数化修复 + 规则解析引擎

#### V5.0 武器注册表元数据层（5 个增量）
- **V5.0 P0**: 武器注册表升级 - 元数据层增量 + 类型别名 + 迁移工具（24 测试）
- **V5.0 P1**: 能力元数据层 - CapabilityProfile + ScenarioMatcher + CapabilityComparator（27 测试）
- **V5.0 P2**: 关系元数据层 - DependencyGraph + ImpactAnalyzer + TransitiveResolver（31 测试）
- **V5.0 P3**: 健康元数据层 - HealthHistory + NaturalSelectionEngine + HealthRanker（33 测试）
- **V5.0 P4**: 生命周期元数据层 - LifecycleEventLog + TransitionGuard + BatchLifecycleManager（38 测试）

#### V5.0 Panel 系统
- `core/panel.py` — PanelDefinition / PanelComponent / Layout / ComponentType
- `core/panel_decision.py` — DecisionFlow 状态机
- `core/panel_generator.py` — 元数据驱动的 Panel 生成器
- `core/panel_adapters.py` — 老数据 → Panel 适配器
- `renderers/cli_renderer.py` — CLI 渲染引擎
- `frontend/src/components/PanelRenderer.tsx` — Next.js 前端渲染器
- `frontend/src/lib/panel.types.ts` — Panel TypeScript 类型
- `frontend/src/app/panels/page.tsx` — Panel 演示页面
- FastAPI 接口：`POST /api/panels/generate`, `POST /api/decisions/submit`, `GET /api/decisions`

#### NiceGUI 驾驶舱
- 根目录 `app.py`（354 行，NiceGUI 版）
- `start_nicegui.py` 启动脚本

#### 第三方审计
- `audit_materials/` — V2 完整审计材料
- `audit_materials_v2/` — V3.0/V4.0/V5.0 审计材料

### Changed
- `workspace/frost-sop/app.py`（Streamlit 版，100KB）已标记 deprecated，UI 主入口改为 NiceGUI
- `renderers/streamlit_renderer.py` 已删除（统一到 Next.js）
- `skills/orchestration.py` — `_wait_for_decision_and_continue()` 支持非阻塞模式（Streamlit/Web 友好）

### Deprecated
- `workspace/frost-sop/app.py` — 保留供回退，不再主动维护
- `renderers/streamlit_renderer.py` — 已删除
- `v3.0.0-beta` tag — 已被 `v3.0.0` 取代

### Removed
- `app.py.bak_f11_warm`、`app.py.bak_workbench_pre` — 备份文件
- `FROST_WHITEPAPER_GAP_MAPPING.md` 等 5 个报告 — 已归档到 `audit_materials_v2/`

### Test Status
- **全量回归**: 260+ 测试通过（V3.0 基线）
- **V5.0 新增**: 153 测试（24+27+31+33+38）
- **Panel 系统**: 92 测试

### Notes
- 38 个本地 commit 未推送至 origin/master（沙箱拦截，需手动 `git push`）
- 详细变更请见 `V3.0.0_RELEASE_NOTES.md`（如有）
- 后续规划见 `V3.1_DOGFOODING_PLAN.md`（如有）

---

## [2.0.0] - 2026-06-26

### Added
- 事件总线 V2.0.0
  - ancestor / parent / elder 事件订阅
  - 全局事件持久化
- v2.0.0 tag 已建立

### Test Status
- 全量回归：105 passed

---

## [1.0.0-f10-baseline] - 2026-06-23

### 概述
首个正式发布版本，包含 F1-F10 全部功能。

### Added
- F1-F9：核心功能（Store / Skill / SOP / 三代 Agent 架构）
- F10：高级能力（SkillExtractor + 验证激活 + 版本管理 + F6.5 集成）
- F11：项目工作台（指挥官驾驶舱）
- 自我进化（STR-002 SOP）
- 错题本（lesson: 前缀）

### Test Status
- 全量回归：55+ 测试通过

---

[3.0.1]: https://gitee.com/liao_liang_7514/frost-sop/releases/tag/v3.0.1
[3.0.0]: https://gitee.com/liao_liang_7514/frost-sop/releases/tag/v3.0.0
[2.0.0]: https://gitee.com/liao_liang_7514/frost-sop/releases/tag/v2.0.0
[1.0.0-f10-baseline]: https://gitee.com/liao_liang_7514/frost-sop/releases/tag/v1.0.0-f10-baseline
