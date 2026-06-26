# V2.0 → V2.1 审计摘要

> FROST-SOP 从 V1.0 管道模型 → V2.0 事件驱动架构 → V2.1 修补的完整审计

---

## 审计历程

| 阶段 | 日期 | 说明 |
|------|------|------|
| V2.0 首审 | 2026-06-26 | Kimi Work 完成首轮审计，发现 4 P0 + 5 P1 |
| **V2.1 修补** | **2026-06-26** | **全部 9 项修复（P0×4 + P1×5）+ 14 新测试** |
| V2.1 二审 | **现在** | **请求 Kimi Work 验证修复 + 扫描新问题** |

---

## 改造目标（一句话）

将 FROST-SOP 从函数调用串联的管道模型，升级为基于 EventBus 的事件驱动架构，实现系统可观测性、长老审计自动化、组件间松耦合。

---

## 改造前后架构对比

### V1.0 — 管道模型（Pipeline）

```
任务输入 → ancestor.run() → parent.run() → execute_stage() × N → 收割产出
                  ↓
            (手动触发) elder.audit_family()
```

**特点**：线性调用链，函数直接调用，长老审计需手动触发。

### V2.0 — 事件驱动（Event-Driven）

```
任务输入 → ancestor.run() → parent.run() → execute_stage() × N → 收割产出
                  ↓               ↓                ↓
             TASK_DECOMPOSED  STAGE_COMPLETED  STEP_COMPLETED
                  ↓               ↓                ↓
          ┌────────────────── EventBus ──────────────────┐
          ↓                                               ↓
    AGENT_CREATED                                 TASK_COMPLETED
    AGENT_DESTROYED                               (长老自动审计)
```

**特点**：各组件通过 EventBus 发布/订阅事件，松耦合，长老审计自动触发。

---

## 核心变更清单

### 阶段一：基线确认
- 创建 `feature/v2-event-driven` 分支
- V1.0 基线：133 passed

### 阶段二：瞬态生命周期管理（+9 测试）
- `core/agent.py`：新增 `_status`, `_created_at`, `_destroyed_at` 字段
- 新增 `destroy()`（幂等销毁）、`_cleanup()`（资源释放）
- `run()` 中使用 `finally` 块保证 `destroy()` 执行
- 新增 `_write_agent_status()` 写入 `agent_status` 表
- V1.0 兼容：`event_driven=False` 保持原行为

### 阶段三：长老审计自动化（+8 测试）
- `skills/orchestration.py`：新增 `finalize_task()` Skill
- 后台守护线程触发 `_trigger_elder_audit()`
- 审计失败不影响主流程（fail-safe）
- `agents/parent.py`：Skill 从 14 升至 15
- `main.py`：[5.6] 步骤调用 `finalize_task`

### 阶段四：EventBus 事件驱动体系（+49 测试）

**4.1+4.2 EventBus 核心（+23）**
- `core/event_bus.py`（新建 322 行）
  - `Event` 数据类（event_type/source/data/event_id/timestamp）
  - `EventType` 常量类（9 个标准事件类型）
  - `EventBus` 单例（线程安全）
  - `publish()` → 同步分发 + 持久化到 `event_log` 表
- `core/db.py`：新增 `event_log` 表

**4.3 Agent 事件驱动（+9）**
- `core/agent.py`：`__init__` 中 `event_driven=True` 时发布 `AGENT_CREATED`
- `run()` 中步骤成功后发布 `STEP_COMPLETED`
- `destroy()` 中发布 `AGENT_DESTROYED`

**4.4 父辈/祖辈事件驱动（+9）**
- `skills/assemble.py`：孙辈组装完成后发布 `AGENT_CREATED`
- `agents/elder.py`：新增 `subscribe_elder_to_events(elder)`
- `_make_elder_event_handler()` 构建回调处理 `TASK_COMPLETED`

**4.5 整体集成（+8）**
- `main.py`：CLI 入口创建长老 + 订阅
- `app.py`：UI 入口 `init_family()` 创建长老 + 订阅

---

## 测试结果总览

| 类别 | 数量 | 状态 |
|------|------|------|
| V2.0 新增测试 | 66 | ✅ 全部通过 |
| V1.0 保留测试 | 133 | ✅ 无新增失败 |
| 已知老问题 | 14 | FileNotFoundError（路径问题） |
| **全量回归** | **186** | **passed** |

---

## 事件类型列表（9 个）

| 事件类型 | 发布者 | 说明 |
|----------|--------|------|
| `TASK_DECOMPOSED` | 祖辈 | 任务分解完成 |
| `TASK_COMPLETED` | 父辈/main | 任务完成 |
| `TASK_FAILED` | 父辈/main | 任务失败 |
| `STAGE_STARTED` | 祖辈 | 阶段开始 |
| `STAGE_COMPLETED` | 父辈 | 阶段完成 |
| `STAGE_FAILED` | 父辈 | 阶段失败 |
| `STEP_COMPLETED` | 孙辈 | 步骤完成 |
| `AGENT_CREATED` | assemble/Agent | Agent 创建 |
| `AGENT_DESTROYED` | Agent | Agent 销毁 |

---

## Fail-Safe 设计

所有 V2.0 新增功能均采用 fail-safe 原则：

| 场景 | 处理 |
|------|------|
| EventBus 初始化失败 | `subscribe_elder_to_events()` 返回 False |
| `_publish_event()` 异常 | 捕获异常并警告，不抛异常 |
| `_write_agent_status()` 失败 | 捕获异常并警告 |
| `finalize_task` 异步审计失败 | 后台线程异常不传播 |
| 事件持久化失败 | 捕获异常，内存缓冲仍有效 |
| 敏感数据保护（V2.1 新增） | `_sanitize_data()` 递归过滤 9 类敏感键 |
| 循环事件防护（V2.1 新增） | `publish()` 跳过 source == callback.__name__ 的回调 |

---

## V2.1 修补清单（9 项全部完成）

### P0（阻塞）— 4 项已修复

| # | 问题 | 修复方案 | 新测试 |
|---|------|----------|--------|
| P0-1 | F9 表结构字段不匹配 | `energy_log`/`schedule`/`decision_points` CREATE TABLE 直接包含所有列 | 已有 F9/F8 测试验证 |
| P0-2 | F8 决策管理逻辑回归 | 移除 `tasks.decision_status` 不存在列引用；新增 `reject_decision()` | 已有 F8 测试验证 |
| P0-3 | 真实 LLM 模式验证 | 加密 API Key 成功调用 DeepSeek（40 tokens） | 手动 E2E 验证 |
| P0-4 | API Key 加密存储 | `core/secrets.py` + `skills/llm.py` 三级回退（env → secrets → prompt） | 已有 |

### P1（严重）— 5 项已修复

| # | 问题 | 修复方案 | 新测试 |
|---|------|----------|--------|
| P1-5 | 架构定位文档 | V2_ARCHITECTURE.md 顶部新增定位声明 | N/A |
| P1-6 | TASK_DECOMPOSED 事件缺失 | `main.py` SOP 内化完成后发布 | 3 个 |
| P1-7 | 敏感数据无过滤 | `_sanitize_data()` 递归过滤 `api_key`/`token`/`password` 等 9 类 | 7 个 |
| P1-8 | 循环事件无防护 | `publish()` 跳过同名回调（排除 lambda） | 3 个 |
| P1-9 | agents 表 UPSERT | `_write_agent_status()` 改为 `INSERT OR REPLACE` | 1 个 |

### 测试增量

| 指标 | V2.0 首审 | V2.1 修补后 |
|------|-----------|-------------|
| 全量测试 | 186 passed | **200 passed** (+14) |
| V2.0 专项 | 66 passed | 66 passed |
| V2.1 专项 | — | **14 passed** |
| 已知老问题 | 14 failed | 14 failed（无新增） |
