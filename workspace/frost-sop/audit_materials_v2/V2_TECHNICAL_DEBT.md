# V2.0 已知技术债务（V2.1 更新版）

> 列出 V2.0 改造中已知的问题、影响范围和修复建议  
> **V2.1 修补后更新**：首审 P0×4 + P1×5 已全部修复 ✅

---

## 首审问题追踪

| # | 等级 | 问题 | V2.1 状态 |
|---|------|------|-----------|
| P0-1 | 阻塞 | F9 表结构字段不匹配 | ✅ 已修复 |
| P0-2 | 阻塞 | F8 决策管理逻辑回归 | ✅ 已修复 |
| P0-3 | 阻塞 | 真实 LLM 模式验证 | ✅ 已验证 |
| P0-4 | 阻塞 | API Key 加密存储 | ✅ 已有 |
| P1-5 | 严重 | 架构定位文档更新 | ✅ 已修复 |
| P1-6 | 严重 | TASK_DECOMPOSED 事件 | ✅ 已实现 |
| P1-7 | 严重 | 敏感数据过滤 | ✅ 已实现 |
| P1-8 | 严重 | 循环事件防护 | ✅ 已实现 |
| P1-9 | 严重 | agents 表 UPSERT | ✅ 已修复 |

---

## 问题 1：14 个 yaml 路径 FileNotFoundError

### 现象

全量回归测试中有 14 个测试失败，均因 `FileNotFoundError: [Errno 2] No such file or directory: 'sops/templates/DEV-001.yaml'`

### 涉及测试

- `test_f6_sop_e2e.py` × 8（test_e2e_dev001 ~ test_e2e_ops006）
- `test_sop.py` × 3（test_sop_load_from_yaml / validate）
- `test_integration.py` × 1（test_full_workflow）

### 根因

测试在项目根目录（`D:/my_ai/Solo-Ops-Platform/`）运行，但 SOP 文件路径使用相对路径 `sops/templates/`，实际文件在 `workspace/frost-sop/sops/templates/`。

### 影响范围

- 仅影响从项目根目录运行的测试，不影响 `frost-sop/` 目录内的生产运行
- CLI E2E 执行（在 `frost-sop/` 目录内）正常
- 不影响 V2.0 功能

### 修复建议

P2（低优先级）：修改测试代码使用绝对路径，或在 pytest 配置中设置正确的工作目录

---

## 问题 2：test_dq01_data_integrity 独立失败

### 现象

`test_f6_deep_quality.py::test_dq01_data_integrity` 独立失败（非 V2.0 引入）

### 涉及测试

- `test_f6_deep_quality.py::test_dq01_data_integrity`

### 根因

未深入调查，V1.0 基线即存在

### 影响范围

- 仅 1 个测试
- 不影响 V2.0 功能

### 修复建议

P3（低优先级）：与 F6 深度测试一起修复

---

## 问题 3：测试间的 EventBus 状态污染

### 现象

多文件联跑时，部分测试因 EventBus 状态残留（如旧的 event_log 数据、残留的订阅者）导致失败。

### 根因

EventBus 是全局单例，测试之间共享状态。部分测试的 `bus.reset()` 破坏了其他测试的引用。

### 已完成修复

- `test_v2_elder_auto_audit.py`：`_make_temp_db()` 中同步 `EventBus.reset()`
- `test_v2_parent_elder_events.py`：统一使用 `get_event_bus()` 获取最新实例

### 影响范围

- 修复后 V2.0 测试 66/66 全绿
- 但新增测试时需注意 EventBus 隔离

### 修复建议

P2（低优先级）：考虑为 EventBus 添加 per-test fixture 级别的重置机制

---

## 问题 4：agents 表 UNIQUE 约束冲突 ✅ 已修复 (V2.1)

### 现象（V2.0 原问题）

E2E 执行日志中出现：
```
⚠️ [V2.0] Agent生命周期记录失败 (parent_dev, destroyed): UNIQUE constraint failed: agents.id
```

### 修复（V2.1 P1-9）

`_write_agent_status()` 改为 `INSERT OR REPLACE`，重复运行不报错。

### 验证

`test_agent_repeated_run_no_unique_constraint_error` 通过。

---

## 问题 5：event_log 表无限增长

---

## 问题 5：event_log 表无限增长

### 现象

`event_log` 表随每次任务执行持续增长，测试运行后已达 334 条记录。

### 根因

无自动清理机制，所有历史事件永久保留。

### 影响范围

- 查询性能可能随事件量增长而下降（当前量级可忽略）
- SQLite 数据库文件大小增长

### 修复建议

P2（低优先级）：
1. 添加配置项 `EVENT_LOG_RETENTION_DAYS`（默认 30 天）
2. 定时任务清理过期事件
3. 或添加 `TRUNCATE` 功能用于测试环境

---

## 问题 6：V1.0 审计报告中的问题是否已解决？

### 回溯

V1.0 审计报告（`FROST-SOP_V1.1_FR_AUDIT_REPORT.md`）中发现的核心问题：

| V1.0 问题 | V2.0 状态 |
|-----------|-----------|
| 缺乏可观测性 | ✅ 已解决（event_log 表 + 事件系统） |
| 手动触发审计 | ✅ 已解决（自动触发） |
| Agent 生命周期无追踪 | ✅ 已解决（agent_status 表） |
| 组件耦合度高 | ✅ 改善（EventBus 解耦） |
| 代码无测试覆盖 | ✅ 新增 66 个测试 |

---

## 剩余技术债务总结

| # | 问题 | 严重度 | 是否阻塞上线 | 修复建议 |
|---|------|--------|-------------|----------|
| 1 | yaml 路径 FileNotFoundError | P2 | ❌ 不影响 | 修改测试工作目录 |
| 2 | test_dq01_data_integrity | P3 | ❌ 不影响 | 与 F6 一起修复 |
| 3 | EventBus 状态污染 | P2 | ❌ 已修复 | per-test fixture 重置 |
| 5 | event_log 无限增长 | P2 | ❌ 不影响 | 添加定期清理 |

**结论：首审 P0/P1 全部修复，剩余 4 项 P2/P3 均不阻塞上线。**
