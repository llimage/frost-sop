# FROST-SOP V3.0 设计文档

> **核心控制流事件驱动架构升级**
>
> 状态：草稿 | 作者：WorkBuddy（技术合伙人）| 日期：2026-06-26
>
> 前置：V2.2 修补完成 + Kimi Work 二审通过 + v2.0.0 基线建立

---

## 1. 架构目标

### 1.1 一句话

将 FROST-SOP 的核心控制流从「函数调用串联的管道模型」彻底改造为「EventBus 驱动的事件架构」，完整实现 FROST 宪法第一条。

### 1.2 V2.2 → V3.0 的质变

| 维度 | V2.2（可观测性事件层） | V3.0（控制流事件驱动） |
|------|----------------------|----------------------|
| 任务启动 | `main()` → `ancestor.run()` 直接调用 | `main()` → publish `TASK_CREATED` |
| 任务分解 | `ancestor.run()` → LLM 分解 → 返回 | ancestor 订阅 `TASK_CREATED` → 分解 → publish `TASK_DECOMPOSED` |
| 阶段调度 | `main()` for 循环 → `parent.run("execute_stage")` | parent 订阅 `TASK_DECOMPOSED` → 逐阶段执行 → publish `STAGE_STARTED/COMPLETED` |
| 孙辈创建 | `execute_stage()` → `assemble_agent()` → `parent.spawn()` | 订阅 `STAGE_STARTED` → 组装 → publish `AGENT_CREATED` |
| 长老审计 | main() 主动调用 `finalize_task` | 长老订阅 `TASK_COMPLETED` → 自动审计（V2.0 已实现） |
| 组件关系 | 硬编码调用链（main → ancestor → parent → child） | 松耦合订阅链（事件驱动，订阅者自行注册） |
| 中断恢复 | ❌ 不支持 | ✅ 从 event_log 恢复状态 |

### 1.3 三条核心原则

1. **消除直接调用链**：`ancestor.run()` 不再直接调用 `parent.run()`
2. **EventBus 驱动一切**：所有组件通过事件通信，无例外
3. **状态外化**：任务进度存储在 event_log 中，支持中断恢复

---

## 2. 控制流改造全景

### 2.1 V2.2 当前控制流（管道模型）

```
main()
 │
 ├── ancestor.run(["call_llm"])         ← 直接调用，等待 LLM 分解
 │
 ├── parent.run(["internalize_sop"])    ← 直接调用
 │
 ├── for stage in stages:               ← for 循环硬编码
 │       parent.run(["execute_stage"])
 │           └── assemble_agent()
 │           └── parent.spawn(child)
 │           └── child.run(sop_steps)
 │
 ├── parent.run(["finalize_task"])      ← 直接调用
 │       └── 后台线程 → elder 审计
 │
 └── print("完成")
```

### 2.2 V3.0 目标控制流（事件驱动）

```
main()
 │
 ├── publish TASK_CREATED
 │
 └── asyncio.run(event_loop)   ← 进入事件循环
      │
      ├── ancestor 订阅 TASK_CREATED
      │       ├── LLM 分解任务
      │       └── publish TASK_DECOMPOSED
      │
      ├── parent 订阅 TASK_DECOMPOSED
      │       ├── 内化 SOP
      │       ├── for stage in stages:
      │       │       publish STAGE_STARTED
      │       │       │
      │       │       ├── execute_stage 订阅 STAGE_STARTED
      │       │       │       ├── assemble_agent()
      │       │       │       ├── child.run()
      │       │       │       └── publish STAGE_COMPLETED
      │       │       │
      │       │       └── parent 收到 STAGE_COMPLETED → 下一阶段
      │       │
      │       └── publish TASK_COMPLETED
      │
      ├── elder 订阅 TASK_COMPLETED
      │       └── audit_family()
      │
      └── reporter 订阅 TASK_COMPLETED
              └── 生成报告 / 持久化
```

### 2.3 关键变更清单

| # | 变更项 | 文件 | 影响 |
|---|--------|------|------|
| C1 | main() 不再直接调用 ancestor.run()，改为 publish TASK_CREATED | `main.py` | 大 |
| C2 | ancestor 从被调用变为订阅 TASK_CREATED | `agents/ancestor.py` | 大 |
| C3 | parent 从被调用变为订阅 TASK_DECOMPOSED | `agents/parent.py` | 大 |
| C4 | execute_stage 从被调用变为订阅 STAGE_STARTED | `skills/orchestration.py` | 大 |
| C5 | 新增 TASK_CREATED 事件类型 | `core/event_bus.py` | 小 |
| C6 | EventBus 从同步发布变为异步发布（asyncio） | `core/event_bus.py` | 大 |
| C7 | main() 进入 asyncio.run() 事件循环 | `main.py` | 中 |
| C8 | 订阅者回调改为 async 函数 | 各 Agent/Skill | 中 |
| C9 | 任务状态持久化 + 中断恢复 | `core/event_bus.py` + 新建 | 中 |
| C10 | 新增 event_driven=True 模式（V3.0 默认） | `core/agent.py` | 中 |

---

## 3. 异步改造方案

### 3.1 为什么需要异步

- V2.2 的 EventBus.publish() 是同步的（阻塞），适合「可观测性事件」（fire-and-forget）
- V3.0 的控制流事件需要「发布-等待-响应」模式：发布 TASK_CREATED 后，需要等待 ancestor 完成分解
- asyncio 是 Python 标准库，无需额外依赖
- Agent.run() 方法本身是同步的（调用 LLM API），可以通过 `asyncio.to_thread()` 包装

### 3.2 AsyncEventBus 设计

```python
class AsyncEventBus(EventBus):
    """
    V3.0 异步事件总线。
    继承 V2.2 EventBus，将 publish() 改为异步版本。
    """

    async def publish(self, event: Event) -> int:
        """异步发布事件：通知所有 async 订阅者，等待全部完成"""
        # 1. 记录到内存缓冲（复用父类）
        # 2. 持久化（复用父类）
        # 3. 异步分发给所有匹配订阅者
        tasks = [callback(event) for callback in callbacks]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        # 处理异常...
        return len(callbacks)

    def subscribe_async(self, event_type: str, callback: Callable[[Event], Awaitable[None]]):
        """注册异步订阅者"""
        ...
```

### 3.3 订阅者 async 改造示例

```python
# V2.2（同步）
def _on_task_completed(event):
    audit_family(ctx)
    print("审计完成")

bus.subscribe(EventType.TASK_COMPLETED, _on_task_completed)

# V3.0（异步）
async def _on_task_completed_async(event: Event):
    ctx = {...}
    audit_family(ctx)  # 同步 Skill，保持不变
    logger.info("审计完成")

bus.subscribe_async(EventType.TASK_COMPLETED, _on_task_completed_async)
```

### 3.4 main() 异步入口

```python
# V3.0 main() 改造
async def main_async(task_input, sop_id):
    bus = get_event_bus()

    # 注册所有组件订阅
    ancestor = create_ancestor(...)
    parent = create_parent(...)
    elder = create_elder(...)

    register_ancestor_subscriptions(ancestor, bus)
    register_parent_subscriptions(parent, bus)
    register_elder_subscriptions(elder, bus)

    # 发布启动事件
    task_id = f"task_{uuid.uuid4().hex[:12]}"
    bus.publish_async(Event(
        event_type=EventType.TASK_CREATED,
        source="main:entry",
        data={"task_input": task_input, "sop_id": sop_id, "task_id": task_id}
    ))

    # 等待任务完成
    await bus.wait_for(EventType.TASK_COMPLETED, timeout=600)

# CLI 入口
if __name__ == "__main__":
    asyncio.run(main_async(args.task, args.sop))
```

### 3.5 同步 Skill 的异步包装

FROST-SOP 的所有 Skill.execute() 都是同步的。V3.0 不要求 Skill 改为 async，而是通过 `asyncio.to_thread()` 包装：

```python
async def execute_stage_async(context):
    """异步版本的 execute_stage"""
    return await asyncio.to_thread(execute_stage_skill.execute, context)
```

---

## 4. 任务状态持久化

### 4.1 设计目标

- 任务执行过程中，所有状态变更都记录在 event_log 中
- 系统崩溃/重启后，可以从 event_log 恢复未完成的任务
- 不需要额外的状态表（event_log 即状态源）

### 4.2 恢复算法

```python
async def recover_incomplete_tasks(bus: AsyncEventBus):
    """
    从 event_log 恢复未完成的任务。
    逻辑：
    1. 查询所有 event_log，找到「有 TASK_CREATED 但无 TASK_COMPLETED/TASK_FAILED」的任务
    2. 从最后一条事件恢复上下文
    3. 重新发布最后的事件类型，让订阅者从中断点继续
    """
    conn = get_db().get_connection()
    # 找到未完成的任务
    rows = conn.execute("""
        SELECT DISTINCT data->>'$.task_id' as task_id
        FROM event_log
        WHERE event_type = 'task_created'
        AND data->>'$.task_id' NOT IN (
            SELECT DISTINCT data->>'$.task_id'
            FROM event_log
            WHERE event_type IN ('task_completed', 'task_failed')
        )
    """).fetchall()

    for row in rows:
        task_id = row[0]
        # 找到最后一条事件
        last_event = conn.execute("""
            SELECT event_type, source, data, timestamp
            FROM event_log
            WHERE data->>'$.task_id' = ?
            ORDER BY timestamp DESC LIMIT 1
        """, (task_id,)).fetchone()

        # 从中断点恢复
        event = Event(last_event[0], last_event[1],
                      json.loads(last_event[2]))
        logger.info(f"恢复未完成任务: {task_id}，从 {event.event_type} 继续")
        await bus.publish(event)
```

### 4.3 中断恢复的支持范围

| 中断点 | 恢复行为 |
|--------|---------|
| TASK_CREATED 后 | 重新发布 TASK_CREATED，ancestor 重新分解 |
| TASK_DECOMPOSED 后 | 重新发布 TASK_DECOMPOSED，parent 从阶段 0 开始 |
| STAGE_COMPLETED 后 | 重新发布 STAGE_COMPLETED，parent 继续下一阶段 |
| STAGE_STARTED 后（阶段中途） | 重新发布 STAGE_STARTED，阶段重新执行（幂等） |

---

## 5. 向后兼容策略

### 5.1 双模式并存

```python
class Agent:
    def __init__(self, ..., event_driven: bool = False):
        """
        V3.0 变更: event_driven 默认值改为 True（新增 V3.0 模式）

        - event_driven=False（V2.2 兼容模式）：Agent 行为不变，main() 保持管道调用
        - event_driven=True（V3.0 模式）：Agent 订阅事件、main() 进入异步循环
        """
```

### 5.2 渐进式迁移路径

```
V2.2 (event_driven=False, 默认)     ← 当前状态
    │
    ├── V3.0-alpha (event_driven=True, 可选)
    │       新功能通过 event_driven=True 启用
    │       旧功能保持 event_driven=False
    │
    ├── V3.0-beta (event_driven=True, 默认)
    │       CLI/UI 默认启用事件驱动
    │       event_driven=False 仍可用作回退
    │
    └── V3.0-stable (移除 event_driven=False)
           所有路径均为事件驱动
           V2.2 兼容层代码移除
```

### 5.3 不修改的模块

以下 V2.2 核心模块在 V3.0 中 **不修改**：

| 模块 | 原因 |
|------|------|
| `core/store.py` | 纯数据存储，与控制流无关 |
| `core/skill.py` | Skill 抽象不变，execute() 签名不变 |
| `core/agent.py` | 原子类，只扩展 event_driven 参数，不加 async |
| `core/sop.py` | SOP 解析不变 |
| `core/db.py` | 数据库层不变（只增加 event_log 查询辅助方法） |
| `core/decision_manager.py` | 决策管理不变 |
| `skills/llm.py` | LLM 调用不变（同步调用） |
| `stores/` 目录 | 存储工厂不变 |

---

## 6. 测试策略

### 6.1 新增测试范围

| 测试文件 | 测试数（预估） | 覆盖内容 |
|----------|:---:|------|
| `tests/test_v3_async_event_bus.py` | 15 | AsyncEventBus publish/subscribe/wait_for |
| `tests/test_v3_ancestor_subscription.py` | 8 | ancestor 订阅 TASK_CREATED 后正确分解 |
| `tests/test_v3_parent_subscription.py` | 10 | parent 订阅 TASK_DECOMPOSED 后逐阶段执行 |
| `tests/test_v3_control_flow_e2e.py` | 12 | 端到端事件链路（TASK_CREATED → COMPLETED） |
| `tests/test_v3_recovery.py` | 8 | 中断恢复（模拟崩溃后从 event_log 恢复） |
| `tests/test_v3_backward_compat.py` | 8 | event_driven=False 模式回归 |
| **合计** | **~61** | |

### 6.2 全量回归

- V2.2 专项测试（80 个）：全部保留，在 event_driven=False 下运行
- V3.0 新增测试（~61 个）：在 event_driven=True 下运行
- 预期全量：~275 passed（V2.2 214 + V3.0 ~61）

---

## 7. 工作量估算

| 阶段 | 内容 | 预估工时 |
|------|------|:---:|
| **设计** | 本文档评审 + 修订 | 2 天 |
| **开发 P1** | AsyncEventBus 实现 | 2 天 |
| **开发 P2** | ancestor/parent 订阅改造 | 3 天 |
| **开发 P3** | execute_stage/assemble 订阅改造 | 3 天 |
| **开发 P4** | main() 异步入口改造 | 2 天 |
| **开发 P5** | 中断恢复机制 | 3 天 |
| **开发 P6** | app.py UI 入口改造 | 2 天 |
| **测试** | V3.0 专项测试（~61 个） | 5 天 |
| **修复** | 回归修复 + 集成调试 | 3 天 |
| **文档** | V3.0 审计材料包 | 1 天 |
| **总工期** | | **~4 周** |

### 7.1 风险项

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|:---:|------|------|
| asyncio 与同步 Skill 的线程安全问题 | 中 | 数据竞争 | 所有同步 Skill 通过 `asyncio.to_thread()` 隔离 |
| EventBus 异步化后的死锁 | 低 | 任务卡住 | publish 加超时机制（默认 300s） |
| 中断恢复逻辑不完整 | 中 | 部分任务无法恢复 | 增量恢复（先支持 80% 场景） |
| agent.py 修改波及面过大 | 低 | 回归失败 | 只扩展参数，不改核心逻辑 |
| UI（app.py/Streamlit）异步适配 | 中 | UI 线程阻塞 | 使用 `asyncio.run_coroutine_threadsafe()` |

---

## 8. 里程碑

| 里程碑 | 内容 | 预估日期 |
|--------|------|:---:|
| M0 | V3.0 设计文档评审通过 | Day 5 |
| M1 | AsyncEventBus 实现 + 测试 | Day 7 |
| M2 | ancestor/parent 订阅改造完成 | Day 10 |
| M3 | execute_stage 订阅改造完成 | Day 13 |
| M4 | main() + app.py 异步入口完成 | Day 15 |
| M5 | 中断恢复完成 | Day 18 |
| M6 | V3.0 全量测试通过 | Day 23 |
| M7 | 第三方审计 | Day 30 |
| M8 | v3.0.0 基线建立 | Day 30+ |

---

## 9. 待决策项

以下事项需要在设计评审中确认：

1. **AsyncEventBus 是继承 EventBus 还是全新实现？**
   - 建议：继承 EventBus，复用水库、持久化、敏感过滤逻辑
2. **wait_for() 的超时策略？**
   - 建议：默认 600s，可配置，超时后发布 TASK_FAILED
3. **中断恢复的首发范围？**
   - 建议：先支持「阶段间恢复」（TASK_DECOMPOSED/STAGE_COMPLETED），阶段内恢复后续迭代
4. **event_driven=True 何时成为默认？**
   - 建议：V3.0-beta（M6 之后）切换默认，V3.0-alpha 保持 opt-in

---

*文档版本：v1.0-draft | 最后更新：2026-06-26*
