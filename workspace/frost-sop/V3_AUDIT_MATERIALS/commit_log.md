# V3.0 提交历史与代码变更

> 生成日期：2026-06-26 | 分支：feature/v2-event-driven | 基线：v2.0.0

---

## 提交历史

```
54632d6  V3.0-05: main() 异步入口改造
e132bef  V3.0-04: execute_stage 事件订阅改造
6cfb72c  V3.0-03: parent 事件订阅改造
4499181  V3.0-02: ancestor 事件订阅改造 + TASK_CREATED 事件类型
99e6307  V3.0-01: AsyncEventBus 独立实现 + TASK_TIMEOUT 事件类型
```

基线：`e30483f V2.2: logging统一 + event_log清理/索引 + source命名统一 + V3设计文档 + 全量源码入库`
标签：`v2.0.0`（在 e30483f 上打）

---

## 文件变更统计

```
 workspace/frost-sop/agents/ancestor.py             |  70 ++++-
 workspace/frost-sop/agents/parent.py               | 172 +++++++++++--
 workspace/frost-sop/core/event_bus.py              | 225 +++++++++++++++++
 workspace/frost-sop/main.py                        | 143 ++++++++++-
 workspace/frost-sop/skills/orchestration.py        |  81 ++++++
 .../frost-sop/tests/test_v3_ancestor_subscribe.py  | 171 +++++++++++++
 .../frost-sop/tests/test_v3_async_event_bus.py     | 281 +++++++++++++++++++++
 .../frost-sop/tests/test_v3_execute_stage_subscribe.py | 182 +++++++++++++
 .../frost-sop/tests/test_v3_main_async.py          | 141 +++++++++++
 .../frost-sop/tests/test_v3_parent_subscribe.py    | 264 +++++++++++++++++++
 10 files changed, 1709 insertions(+), 21 deletions(-)
```

---

## 逐提交变更详情

### V3.0-01: AsyncEventBus 独立实现 + TASK_TIMEOUT 事件类型
**Commit:** `99e6307`

**变更文件：**
- `core/event_bus.py` (+225) — AsyncEventBus 完整类 + TASK_CREATED/TASK_TIMEOUT 事件类型
- `tests/test_v3_async_event_bus.py` (+281) — 12 个测试

**关键设计：**
- AsyncEventBus 不继承 EventBus，独立实现
- 使用 asyncio.Lock（非 threading.Lock）
- 同步回调通过 asyncio.to_thread() 执行
- 单例模式：`get_async_event_bus()` 返回全局唯一实例

### V3.0-02: ancestor 事件订阅改造 + TASK_CREATED 事件类型
**Commit:** `4499181`

**变更文件：**
- `agents/ancestor.py` (+70) — create_ancestor 新增 event_driven 参数 + _subscribe_ancestor_to_events
- `tests/test_v3_ancestor_subscribe.py` (+171) — 5 个测试

**关键逻辑：**
- event_driven=True 时，订阅 TASK_CREATED
- 回调中调用 ancestor.run(["call_llm"]) 分解任务
- 分解完成后发布 TASK_DECOMPOSED 事件
- event_driven=False（默认）时，无任何事件订阅副作用

### V3.0-03: parent 事件订阅改造
**Commit:** `6cfb72c`

**变更文件：**
- `agents/parent.py` (+172) — create_parent 新增 event_driven/asset_store/sop_id 参数 + _subscribe_parent_to_events
- `tests/test_v3_parent_subscribe.py` (+264) — 8 个测试

**关键逻辑：**
- event_driven=True 时，订阅 TASK_DECOMPOSED
- 回调中：加载 SOP → 内化 SOP → 逐阶段执行（发布 STAGE_STARTED/STAGE_COMPLETED）
- 全部阶段完成后发布 TASK_COMPLETED
- SOP 加载失败发布 TASK_FAILED

### V3.0-04: execute_stage 事件订阅改造
**Commit:** `e132bef`

**变更文件：**
- `skills/orchestration.py` (+81) — 新增 register_stage_executor 函数
- `tests/test_v3_execute_stage_subscribe.py` (+182) — 6 个测试

**关键逻辑：**
- register_stage_executor(parent, asset_store) 注册 STAGE_STARTED 异步订阅
- 回调中调用 parent.run(["execute_stage"]) 执行阶段
- 执行完成后发布 STAGE_COMPLETED 事件

### V3.0-05: main() 异步入口改造
**Commit:** `54632d6`

**变更文件：**
- `main.py` (+143) — 新增 main_async() + CLI --async-mode/--timeout 参数
- `tests/test_v3_main_async.py` (+141) — 5 个测试

**关键逻辑：**
- main_async() 创建组件(event_driven=True) → 注册订阅 → 发布 TASK_CREATED → 等待终止事件
- 支持 timeout 参数（默认 600s），超时发布 TASK_TIMEOUT
- CLI 入口负责 AsyncEventBus.reset()，main_async 本身不 reset
- 保留原有 main() 同步入口（V2.0 兼容）

**修复记录：**
- `args.async` 语法错误 → 改为 `--async-mode` / `args.async_mode`
- main_async 内部 reset 清除测试订阅者 → 移除 reset，由调用方管理

---

## 代码审查要点

| 审查项 | 状态 | 说明 |
|--------|------|------|
| AsyncEventBus 不继承 EventBus | ✅ | 独立类，无继承关系 |
| 使用 asyncio.Lock | ✅ | 非 threading.Lock |
| 同步/异步订阅者共存 | ✅ | 同步回调通过 to_thread 执行 |
| event_driven 默认 False | ✅ | V2.0 兼容 |
| TASK_TIMEOUT ≠ TASK_FAILED | ✅ | 独立事件类型 |
| main_async 不内部 reset | ✅ | 由 CLI/测试负责清理 |
| V2.0 main() 保留 | ✅ | 同步入口未修改 |
| 所有 V2.0 测试零修改通过 | ✅ | 214 passed |
