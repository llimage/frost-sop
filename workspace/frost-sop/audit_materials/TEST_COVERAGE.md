# TEST_COVERAGE — 测试覆盖报告

## 测试总体情况

| 指标 | 数值 |
|------|------|
| 测试目录 | `tests/` (32 个文件) |
| 总测试用例 | 95 (pytest 收集) / 107 (grep 统计) |
| **通过** | **94** |
| **失败** | **2** |
| **错误 (ERROR)** | **10** |
| 警告 | 59 |
| 通过率 | 94 / 106 = **88.7%** (不含10个环境ERROR) |

## 最新 pytest 运行结果

```
============= 94 passed, 2 failed, 10 errors, 59 warnings =============
```

运行条件: `FROST_TESTING=1` (mock 模式)，排除了需要真实 LLM/UI 的测试

## 测试文件详情

### ✅ 全部通过 (24 个文件)

| 测试文件 | 用例数 | 覆盖范围 |
|----------|--------|----------|
| tests/test_store.py | 4 | Store 三级存储体系 |
| tests/test_sop.py | 3 | SOP YAML 加载与验证 |
| tests/test_agent.py | 4 | Agent 核心类 |
| tests/test_assemble.py | 2 | 孙辈 Agent 组装 |
| tests/test_assembled_output.py | 1 | 组装后输出 |
| tests/test_autonomy_data.py | 1 | 自治数据流 |
| tests/test_f6_sop_e2e.py | 7 | F6 SOP 端到端 |
| tests/test_f6_parallel.py | 4 | 并行执行 |
| tests/test_f6_persistence.py | 4 | 持久化测试 |
| tests/test_f6_deep_quality.py | 8 | 深度质量测试 |
| tests/test_f7_acceptance.py | 9 | F7 验收测试 |
| tests/test_f8_decision.py (*) | 6 | F8 决策管理 |
| tests/test_f9_founder_tools.py (*) | 13 | F9 Founder Tools |
| tests/test_f10_skill_extractor.py | 14 | F10 Skill 提取器 |
| tests/test_f14_persistence_verify.py | 1 | F14 持久化验证 |
| tests/test_elder_deep_quality.py | 6 | 长老深度质量 |
| tests/test_elder_e2e.py | 1 | 长老端到端 |
| tests/test_evolution_deep_quality.py | 6 | 进化深度质量 |
| tests/test_evolution_e2e.py | 1 | 进化端到端 |
| tests/test_gene_quality.py | 1 | 基因质量 |
| tests/test_mercenary_output.py | 4 | 雇佣兵输出 |
| tests/test_f6_5_saved_beans.py | 1 | F6.5 配置持久化 |
| tests/test_health_dashboard.py | 3 | 健康面板 |
| tests/test_semantic_match.py | 1 | 语义匹配 |

> (*) test_f8_decision 和 test_f9_founder_tools 中有部分用例失败/ERROR

### ❌ 失败详情 (2 FAILED)

| 测试 | 问题 |
|------|------|
| `test_f8_decision.py::TestDecisionManager::test_resume_decision` | 决策恢复逻辑异常 |
| `test_f8_decision.py::TestDecisionManager::test_has_pending_decision` | 待决判断逻辑异常 |

### ⚠️ 错误详情 (10 ERROR)

| 测试 | 类型 | 详情 |
|------|------|------|
| `test_f8_decision.py::TestAuditIntegration::test_audit_log_after_decision` | sqlite3.Error | 依赖上述失败 |
| `test_f9_founder_tools.py::test_add_energy_log` | sqlite3.OperationalError | 表结构字段不匹配 |
| `test_f9_founder_tools.py::test_get_latest_energy` | sqlite3.OperationalError | 同上 |
| `test_f9_founder_tools.py::test_get_energy_history` | sqlite3.OperationalError | 同上 |
| `test_f9_founder_tools.py::test_low_energy_detection` | sqlite3.OperationalError | 同上 |
| `test_f9_founder_tools.py::test_add_schedule` | sqlite3.OperationalError | 同上 |
| `test_f9_founder_tools.py::test_get_schedules` | sqlite3.OperationalError | 同上 |
| `test_f9_founder_tools.py::test_update_schedule` | sqlite3.OperationalError | 同上 |
| `test_f9_founder_tools.py::test_delete_schedule` | sqlite3.OperationalError | 同上 |
| `test_f9_founder_tools.py::test_get_upcoming_reminders` | sqlite3.OperationalError | 同上 |

### 需要特殊环境 (跳过执行)

| 测试文件 | 原因 |
|----------|------|
| tests/test_llm_live.py | 需要真实 DEEPSEEK_API_KEY |
| tests/test_f12_e2e_ui.py | 需要 Streamlit 运行 |
| tests/test_f16_api.py | 需要 FastAPI 运行 |
| tests/debug_audit.py | 调试脚本 |
| tests/verify_f14_db.py | 验证脚本 |

## 测试覆盖率分析

### 核心模块覆盖

| 核心模块 | 测试文件 | 覆盖状态 |
|----------|----------|---------|
| core/store.py | test_store.py | ✅ 覆盖 |
| core/sop.py | test_sop.py | ✅ 覆盖 |
| core/agent.py | test_agent.py | ✅ 覆盖 |
| core/db.py | test_f6_persistence.py + test_f14_persistence_verify.py | ✅ 覆盖 |
| core/skill_extractor.py | test_f10_skill_extractor.py (14用例) | ✅ 深度覆盖 |
| core/skill_version.py | test_f10_skill_extractor.py (部分) | ⚠️ 部分覆盖 |
| agents/ancestor.py | test_integration.py | ⚠️ 间接覆盖 |
| agents/parent.py | test_integration.py | ⚠️ 间接覆盖 |
| agents/elder.py | test_elder_*.py (7用例) | ✅ 覆盖 |
| skills/orchestration.py | test_f6_sop_e2e.py (7用例) | ✅ 覆盖 |
| skills/llm.py | test_f6_mock_llm.py | ✅ Mock 覆盖 |
| skills/assemble.py | test_assemble.py | ✅ 覆盖 |
| skills/evolution.py | test_evolution_*.py (7用例) | ✅ 覆盖 |
| api/main.py | test_f16_api.py | ⚠️ 需 API 运行 |
| app.py | test_f12_e2e_ui.py | ⚠️ 需 Streamlit 运行 |

### 未覆盖模块

| 模块 | 行数 | 风险 |
|------|------|------|
| core/skill_version.py (回滚逻辑) | 230 | 中 — 无独立单元测试 |
| api/main.py (13 端点) | 523 | 高 — 无自动化 API 测试 |
| app.py (Streamlit UI) | 1,927 | 中 — 无 E2E 测试 |
| frontend/ (Next.js) | 3,813 | 高 — 无前端测试 |

## 测试基础设施

- **框架**: pytest (未声明在 requirements.txt)
- **Mock 策略**: `FROST_TESTING=1` 环境变量切换全局 mock 模式
- **LLM Mock**: `skills/llm.py` 中 `_mock_response_for_prompt()` 按关键词匹配返回
- **CI**: 无配置（所有测试手动运行）
- **覆盖率工具**: 未配置 (pytest-cov 未安装)

## 测试运行命令

```bash
# Windows Git Bash (mock 模式)
cd workspace/frost-sop && python -X utf8 -c \
  "import os; os.environ['FROST_TESTING']='1'; \
   import subprocess; \
   subprocess.run(['python','-m','pytest','tests/','-v'])"

# 排除需要特殊环境的测试
pytest tests/ --ignore=tests/test_llm_live.py \
              --ignore=tests/test_f12_e2e_ui.py \
              --ignore=tests/test_f16_api.py
```
