# KNOWN_ISSUES — 已知问题清单

> 问题按严重程度分级：P0 阻塞 / P1 重要 / P2 低优先级

---

## P0 — 阻塞级（影响核心功能）

### P0-1: F9 Founder Tools 表结构字段不匹配
**影响范围**: energy_log / schedule 表的 CRUD 操作
**表现**: 6 个 test_f9_founder_tools 测试用例报 `sqlite3.OperationalError`
**根因**: `core/db.py` 中 energy_log / schedule 表新增了字段（如 `level`, `emotion`, `user_note`），但某些查询 SQL 中未包含新字段，导致 INSERT 时字段数量和值数量不匹配
**影响**: 能量记录和日程管理功能在生产环境不可用
**修复建议**: 统一 `add_energy_log()` / `add_schedule()` 方法的 INSERT SQL 与表结构字段数量和顺序

### P0-2: F8 Decision 管理逻辑异常
**影响范围**: 决策恢复 (`test_resume_decision`) 和待决判断 (`test_has_pending_decision`)
**表现**: 2 FAILED，1 ERROR (级联)
**根因**: 决策点（decision_points）的查询/恢复逻辑在近期重构后出现回归
**影响**: 决策管理功能不可用（无法恢复暂停的任务，无法判断是否有待决）
**修复建议**: 回看 `core/db.py` 中的 decision 相关查询，确认与 test 用例期望一致

---

## P1 — 重要（影响体验或数据质量）

### P1-1: /api/sops 端点未暴露
**影响范围**: 前端日程管理页面
**表现**: `curl http://localhost:8000/api/sops` 返回 404
**根因**: FastAPI 路由定义中不存在 `/api/sops` 端点
**影响**: 前端创建日程时无法选择 SOP 模板，使用 fallback mock 数据
**修复建议**: 在 `api/main.py` 中添加 `GET /api/sops` 端点，查询 `sop_templates` 表

### P1-2: WebSocket 实时日志推送未接入
**影响范围**: 前端 LogTerminal 组件的实时性
**表现**: 日志更新依赖轮询 fallback
**根因**: FastAPI 端的 SSE (`/api/logs`) 已实现，但前端未订阅
**影响**: 日志延迟较长，用户体验不佳
**修复建议**: 在前端 `LogTerminal.tsx` 中订阅 SSE 流 (`EventSource`)

### P1-3: cost_log 历史遗留数据
**影响范围**: 数据清洗
**表现**: 78 条历史记录 `agent_id='unknown'`（F14 前遗留），部分 `task_id` 为 null
**根因**: F14 持久化修复前的代码未写入 agent_id
**影响**: 成本统计按 Agent 维度汇总时数据不完整
**修复建议**: 在 DB 迁移脚本中添加数据清洗步骤（清理或标记旧数据）

### P1-4: chromadb 未在 requirements.txt
**影响范围**: 部署
**表现**: `core/memory.py` 中 `import chromadb`，但 `pip install -r requirements.txt` 不会安装
**根因**: chromadb 未声明为运行时依赖
**影响**: 首次部署时知识库检索功能不可用
**修复建议**: 在 requirements.txt 中添加 `chromadb>=0.4.0`

### P1-5: pytest 未在 requirements.txt
**影响范围**: 测试环境
**表现**: 新环境无法直接运行 `pytest tests/`
**根因**: pytest 未声明为开发依赖
**影响**: CI/CD 集成困难
**修复建议**: 在 requirements.txt 中添加 `pytest>=8.0` 和 `pytest-cov>=5.0`

---

## P2 — 低优先级（优化/美化）

### P2-1: pytest 返回值警告 (PytestReturnNotNoneWarning)
**影响范围**: 7 个测试函数返回 dict/bool 但 pytest 期望 None
**表现**: 59 个 PytestReturnNotNoneWarning
**根因**: 测试辅助函数通过 return 返回 fixture 数据，不符合 pytest 规范
**影响**: 不影响测试通过，但日志嘈杂
**修复建议**: 将返回值改为 yield 或使用 `pytest.fixture`

### P2-2: 前端缺少测试
**影响范围**: 前端可靠性
**表现**: `frontend/` 目录 3,813 行代码无任何测试
**根因**: 前端开发工期紧张，未建立测试体系
**影响**: 重构风险高，Regression 检测困难
**修复建议**: 引入 Vitest + React Testing Library，优先为 api.ts / store.ts 写单元测试

### P2-3: Streamlit UI 无 E2E 测试
**影响范围**: app.py (1,927 行)
**表现**: `test_f12_e2e_ui.py` 需要手动运行 Streamlit
**根因**: Streamlit E2E 测试环境搭建复杂
**影响**: 工作台 UI 变更依赖手动验证
**修复建议**: 使用 Playwright + streamlit-app-test 框架

### P2-4: 缺少 Git pre-commit hook
**影响范围**: 代码质量
**表现**: 无自动 lint / format / test 检查
**影响**: 提交前不运行测试，可能引入回归
**修复建议**: 配置 pre-commit hook 运行 `pytest tests/ -x` + `npx next lint`

### P2-5: debug 文件未清理
**影响范围**: 代码仓库整洁度
**表现**: 根目录残留 `debug_audit.log`, `test_output.txt`, `test_full_output.txt`, `tmpcpjfciuc/` 等
**根因**: 开发调试产物未清理
**影响**: 仓库体积膨胀
**修复建议**: 添加 `.gitignore` 规则，清理已存在的调试文件

---

## 汇总

| 严重度 | 数量 | 风险 |
|--------|------|------|
| P0 — 阻塞 | 2 | 核心功能不可用 |
| P1 — 重要 | 5 | 影响体验/数据/部署 |
| P2 — 优化 | 5 | 技术债务 |
| **总计** | **12** | |

### 建议修复顺序

1. **P0-1** → 修复 F9 表结构字段匹配（1-2 小时）
2. **P0-2** → 修复 F8 决策管理逻辑（1-2 小时）
3. **P1-1** → 暴露 /api/sops 端点（30 分钟）
4. **P1-4** → 补充 requirements.txt（5 分钟）
5. **P1-5** → 补充 requirements.txt（5 分钟）
6. **P1-2** → 接入 SSE 流（2-4 小时）
7. **P1-3** → 数据清洗脚本（1 小时）
8. **P2-5** → 仓库清理（30 分钟）
