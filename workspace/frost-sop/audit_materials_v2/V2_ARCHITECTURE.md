# V2.0 架构设计文档

> **⚠️ V2.0 定位声明（P1-5 修补新增）：**
>
> **V2.0 是「可观测性事件层」，不是「核心控制流事件驱动」。**
>
> - V2.0 在 V1.0 管道模型之上叠加了一个非阻塞事件总线（EventBus）
> - Agent 生命周期（created/running/destroyed）、步骤执行（step_completed）、长老审计（auto_audit）等产生事件，通过 EventBus 分发
> - 但核心控制流（任务分解 → 阶段执行 → 孙辈调度）**仍然由管道模型直接调用完成**
> - `event_driven=False`（默认）保持 V1.0 完全兼容
> - **V3.0 将把控制流也改造为事件驱动**，届时整个系统才是完全事件驱动架构
>
> V2.0 是可观测性升级，不是架构重构。核心流程不受事件层影响。

## 1. EventBus 设计

### 类图

```
┌─────────────────────────────────────────────┐
│                 EventBus                     │
│  (单例, 线程安全)                             │
├─────────────────────────────────────────────┤
│  - _instance: EventBus | None               │
│  - _lock: threading.Lock                    │
│  - _subscribers: dict[str, list[callable]]  │
│  - _event_log: list[Event]                  │
├─────────────────────────────────────────────┤
│  + subscribe(event_type, handler)           │
│  + unsubscribe(event_type, handler)         │
│  + clear_subscribers()                      │
│  + publish(event: Event) → int              │
│  + get_event_log() → list[Event]            │
│  + get_subscriber_count() → int             │
│  + reset()                                  │
└─────────────────────────────────────────────┘
                      │
                      │ 使用
                      ▼
┌─────────────────────────────────────────────┐
│                   Event                      │
├─────────────────────────────────────────────┤
│  + event_type: str                          │
│  + source: str                              │
│  + data: dict                               │
│  + event_id: str                            │
│  + timestamp: str                           │
├─────────────────────────────────────────────┤
│  + to_dict() → dict                         │
└─────────────────────────────────────────────┘
                      │
                      │ 常量
                      ▼
┌─────────────────────────────────────────────┐
│                EventType                     │
├─────────────────────────────────────────────┤
│  TASK_DECOMPOSED = "task_decomposed"        │
│  TASK_COMPLETED = "task_completed"          │
│  TASK_FAILED = "task_failed"                │
│  STAGE_STARTED = "stage_started"            │
│  STAGE_COMPLETED = "stage_completed"        │
│  STAGE_FAILED = "stage_failed"              │
│  STEP_COMPLETED = "step_completed"          │
│  AGENT_CREATED = "agent_created"            │
│  AGENT_DESTROYED = "agent_destroyed"        │
└─────────────────────────────────────────────┘
```

### 接口说明

#### EventBus 核心方法

| 方法 | 说明 | 返回值 |
|------|------|--------|
| `subscribe(event_type, handler)` | 注册事件订阅 | 无 |
| `unsubscribe(event_type, handler)` | 取消订阅 | 无 |
| `publish(event)` | 发布事件（同步分发 + 持久化） | 订阅者数量 |
| `get_event_log()` | 获取内存事件日志 | `list[Event]` |
| `get_subscriber_count()` | 获取总订阅者数 | `int` |

#### 发布流程（`publish`）

```
Event 对象
  │
  ├── 1. 记录到内存缓冲 (_event_log)
  │
  ├── 2. 持久化到 SQLite event_log 表 (fail-safe)
  │      └── 失败 → 仅打印警告，不影响分发
  │
  └── 3. 同步分发给所有匹配订阅者
         ├── 单个订阅者异常 → 仅打印警告，不影响其他
         └── 无匹配订阅者 → 无操作
```

### 单例与线程安全

```python
EventBus._instance  = None  (类变量)
EventBus._lock      = threading.Lock()  (类变量)

get_event_bus():
    if _instance is None:
        with _lock:
            if _instance is None:  # Double-checked locking
                _instance = EventBus()
    return _instance
```

---

## 2. 事件类型定义（9 个）

### EventType 常量类

```python
class EventType:
    # 任务级事件
    TASK_DECOMPOSED = "task_decomposed"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"

    # 阶段级事件
    STAGE_STARTED = "stage_started"
    STAGE_COMPLETED = "stage_completed"
    STAGE_FAILED = "stage_failed"

    # 步骤级事件
    STEP_COMPLETED = "step_completed"

    # Agent 生命周期事件
    AGENT_CREATED = "agent_created"
    AGENT_DESTROYED = "agent_destroyed"
```

### 事件层级关系

```
TASK_DECOMPOSED
  └── STAGE_STARTED
       └── STEP_COMPLETED (每步骤一个)
            └── AGENT_CREATED / AGENT_DESTROYED
       └── STAGE_COMPLETED | STAGE_FAILED
  └── TASK_COMPLETED | TASK_FAILED
       └── (长老审计自动触发)
```

---

## 3. 事件流数据流图

```
用户输入（main.py CLI 或 app.py UI）
         │
         ▼
    [1] 祖辈 Agent ──────→ 发布 TASK_DECOMPOSED
         │
         ▼
    [2] 父辈 Agent ──────→ 发布 STAGE_COMPLETED (每阶段)
         │
         ├── [3] assemble_agent() ──→ 发布 AGENT_CREATED (孙辈)
         │         │
         │         ▼
         │    [4] 孙辈 Agent ──→ 发布 STEP_COMPLETED (每步骤)
         │         │
         │         ▼
         │    [5] destroy() ──→ 发布 AGENT_DESTROYED
         │
         ▼
    [6] finalize_task() ──→ 后台线程
                                  │
                                  ▼
                          [7] 长老 Agent
                            ┌─── audit_family()
                            │         │
                            │         ▼
                            │    audit_log 表 (auto_audit 记录)
                            │
                            └─── 订阅 TASK_COMPLETED (自动触发)
```

---

## 4. 与 V1.0 管道模型的对比

| 维度 | V1.0 管道模型 | V2.0 事件驱动 |
|------|--------------|--------------|
| 组件通信 | 函数直接调用 | EventBus 发布/订阅 |
| 可观测性 | 无（只有 print） | event_log 表持久化 |
| 长老审计 | 手动触发 | 自动触发（订阅 TASK_COMPLETED） |
| Agent 生命周期 | 无追踪 | agent_status 表 + created/destroyed 事件 |
| 扩展性 | 修改调用链 | 新增订阅者 |
| 耦合度 | 高（函数依赖） | 低（事件解耦） |
| 失败隔离 | 调用链失败 = 全部失败 | 单个订阅者失败不影响其他 |
| 向后兼容 | — | event_driven=False 保持 V1.0 行为 |

---

## 5. 持久化设计

### event_log 表结构

```sql
CREATE TABLE IF NOT EXISTS event_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL UNIQUE,
    event_type TEXT NOT NULL,
    source TEXT,
    data TEXT,  -- JSON
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### agent_status 表结构

```sql
CREATE TABLE IF NOT EXISTS agent_status (
    agent_id TEXT PRIMARY KEY,
    status TEXT,           -- idle/running/destroyed
    current_task_id TEXT,
    last_heartbeat TIMESTAMP,
    total_tokens_used INTEGER,
    total_cost REAL,
    error_count INTEGER
);
```

---

## 6. 关键设计决策

### 自建 EventBus vs 使用外部库

**选择**：自建 EventBus（`core/event_bus.py`，322 行）

**理由**：
- FROST-SOP 是轻量级单进程 Python 应用
- 外部库（如 `blinker`, `pypubsub`）引入额外依赖，增加维护负担
- 自建可实现定制化（事件持久化、类别常量、fail-safe 行为）
- 322 行代码量可控，不引入复杂度

### 同步分发 vs 异步分发

**选择**：同步分发

**理由**：
- FROST-SOP 任务执行本身就是同步的（管道模型）
- 异步引入线程管理复杂度，且受益有限
- 长老审计通过后台 `daemon=True` 线程实现异步（不阻塞主流程）
- EventBus.publish() 中的持久化是同步写入，保证一致性
