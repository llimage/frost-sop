# V2.0 代码变更详情

> 每个修改文件的具体变更，按改动量排序

---

## 1. core/event_bus.py（新建，322 行）

**用途**：EventBus 核心实现

**关键类**：

```python
class Event:
    event_type: str    # 事件类型
    source: str        # 发布者标识
    data: dict         # 事件携带数据
    event_id: str      # UUID 唯一标识
    timestamp: str     # ISO 时间戳

class EventType:
    TASK_DECOMPOSED / TASK_COMPLETED / TASK_FAILED / ...
    共 9 个标准事件类型

class EventBus:
    # 单例模式 + threading.Lock
    subscribe(event_type, handler)
    unsubscribe(event_type, handler)
    publish(event: Event) → int
    get_event_log() → list[Event]
    reset()
```

**变更前**：不存在
**变更后**：完整的事件总线基础设施

---

## 2. core/agent.py（修改，+507 行）

**新增属性**：
```python
self._status: str = "idle"
self._created_at: datetime = datetime.now()
self._destroyed_at: Optional[datetime] = None
self._event_driven: bool = False  # V1.0 兼容
```

**新增方法**：

- `destroy()` — 幂等销毁
  ```python
  def destroy(self):
      if self._status == "destroyed": return  # 幂等
      self._status = "destroyed"
      self._write_agent_status("destroyed", ...)
      if self._event_driven:
          self._publish_event("agent_destroyed", ...)
      self._cleanup()
  ```

- `_cleanup()` — 释放资源
- `_write_agent_status(status, task_id)` — 写入 `agent_status` 表
- `_publish_event(event_type, data)` — fail-safe 事件发布

**修改方法**：

- `__init__()`: 新增 `event_driven` 参数（默认 `False`）
- `run()`:
  ```python
  # 修改前
  for step in sop_steps:
      step_result = self._execute_step(...)
      updates[step["name"]] = step_result

  # 修改后
  try:
      self._status = "running"
      for step in sop_steps:
          step_result = self._execute_step(...)
          if step_result["success"] and self._event_driven:
              self._publish_event("step_completed", ...)
  finally:
      self.destroy()  # 保证销毁
  ```

---

## 3. core/db.py（修改，+948 行）

**新增表**：

```sql
CREATE TABLE IF NOT EXISTS event_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL UNIQUE,
    event_type TEXT NOT NULL,
    source TEXT,
    data TEXT,       -- JSON
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**变更前**：18 张表（不含 event_log）
**变更后**：19 张表（含 event_log，实际运行中 23 张含测试用表）

---

## 4. agents/elder.py（修改，+185 行）

**新增函数**：

- `_make_elder_event_handler(elder_agent)` → 构建事件处理回调
  ```python
  def _make_elder_event_handler(elder_agent):
      def handler(event: Event):
          try:
              result = elder_agent.run(
                  sop_steps=["audit_family"],
                  initial_context={"_trigger": "event", ...}
              )
              # 审计结果写入 audit_log
          except Exception as e:
              print(f"[Elder] 自动审计失败: {e}")
      return handler
  ```

- `subscribe_elder_to_events(elder_agent)` → 注册订阅
  ```python
  def subscribe_elder_to_events(elder_agent) → bool:
      try:
          bus = get_event_bus()
          handler = _make_elder_event_handler(elder_agent)
          elder_agent._event_handler = handler  # 保存引用
          bus.subscribe(EventType.TASK_COMPLETED, handler)
          return True
      except Exception as e:
          warnings.warn(f"[Elder] 事件订阅失败（已忽略）: {e}")
          return False
  ```

**变更前**：仅有 `create_elder()` 和 `audit_family` Skill
**变更后**：增加了事件订阅能力，支持自动审计

---

## 5. skills/assemble.py（修改，+311 行）

**新增代码**（在组装完成处）：
```python
try:
    bus = get_event_bus()
    bus.publish(Event(
        event_type=EventType.AGENT_CREATED,
        source="assemble_agent",
        data={
            "agent_name": child.name,
            "generation": child.generation,
            "skill_count": len(assembled_skills),
            "task_id": context.get("_task_id", ""),
        },
    ))
except Exception as e:
    print(f"[V2.0 assemble] 事件发布失败（已忽略）: {e}")
```

**变更前**：组装完成后仅设置 context
**变更后**：组装完成后发布 `AGENT_CREATED` 事件（fail-safe）

---

## 6. main.py（修改，+336 行）

**导入变更**：
```python
# 新增
from agents.elder import create_elder, subscribe_elder_to_events
```

**初始化变更**（在 ancestor 创建后）：
```python
# 新增
elder = create_elder("elder_main", asset_store=asset_store)
if subscribe_elder_to_events(elder):
    print("   [V2.0] 长老已订阅 TASK_COMPLETED 事件")
else:
    print("   [V2.0] 长老事件订阅跳过（EventBus 不可用）")
```

**变更前**：祖辈 → 父辈 → 执行 SOP
**变更后**：祖辈 → 长老订阅 → 父辈 → 执行 SOP → 长老自动审计

---

## 7. app.py（修改，+2375 行）

**导入变更**：
```python
# 修改前
from agents.elder import create_elder
# 修改后
from agents.elder import create_elder, subscribe_elder_to_events
```

**init_family() 变更**：
```python
# 在 st.session_state.initialized = True 之后新增
elder = create_elder("elder_ui", asset_store=st.session_state.asset_store)
if subscribe_elder_to_events(elder):
    add_log("✅ [V2.0] 长老已订阅 TASK_COMPLETED 事件")
else:
    add_log("⚠️ [V2.0] 长老事件订阅跳过（EventBus 不可用）")
```

---

## 8. skills/orchestration.py（修改，+488 行）

**新增函数**：

- `_trigger_elder_audit(task_id, asset_store, constitution_store)` — 在后台线程中执行长老审计
- `finalize_task(context)` — 新建 Skill，任务完成时调用

**新增 Skill 实例**：
```python
finalize_task_skill = Skill("finalize_task", finalize_task)
```

---

## 9. agents/parent.py（修改，+68 行）

**新增导入**：
```python
from skills.orchestration import finalize_task_skill
```

**新增 Skill 注册**：
```python
# Skill 从 14 升至 15
skills["finalize_task"] = finalize_task_skill
```

---

## 10. 测试文件（新增，7 个文件，+1313 + new 行）

| 文件 | 行数 | 测试数 | 阶段 |
|------|------|--------|------|
| tests/test_v2_lifecycle.py | 164 | 9 | V2.0 |
| tests/test_v2_elder_auto_audit.py | 209 | 8 | V2.0 |
| tests/test_v2_event_bus.py | 321 | 23 | V2.0 |
| tests/test_v2_agent_event_driven.py | 191 | 9 | V2.0 |
| tests/test_v2_parent_elder_events.py | 258 | 9 | V2.0 |
| tests/test_v2_subphase45_integration.py | 170 | 8 | V2.0 |
| tests/test_v2_patch_p1.py | ~200 | 14 | **V2.1** |
| **合计** | **~1513** | **80** | |

---

## 11. V2.1 修补变更（核心文件 5 个）

### 11.1 core/db.py — P0-1：表结构修复

**问题**：`energy_log`, `schedule`, `decision_points` 三张表的 CREATE TABLE 缺少部分列，依赖 migration 补充。

**修复**：CREATE TABLE 直接包含所有列，消除迁移依赖。

```diff
  energy_log: 新增 energy_level, health_score 列为 CREATE TABLE 直接定义
  schedule: 新增 sop_id, sop_params, priority 列为 CREATE TABLE 直接定义
  decision_points: 新增 stage_id, user_decision, user_note, responded_at, decision_type 列
```

### 11.2 core/decision_manager.py — P0-2：决策管理器修复

**问题**：`resume_decision()` 引用不存在的 `tasks.decision_status` 列导致 UPDATE 失败。

**修复**：
- 移除对 `tasks.decision_status` 的不存在列引用
- 新增 `reject_decision()` 方法（显式拒绝操作）
- 添加 `threading.Lock` 线程安全保护

### 11.3 core/agent.py — P1-9：agents 表 UPSERT

**问题**：重复运行 `_write_agent_status()` 触发 UNIQUE 约束错误。

**修复**：`INSERT` → `INSERT OR REPLACE`

### 11.4 core/event_bus.py — P1-7 + P1-8：安全加固

**P1-7 敏感数据过滤**：
```python
_SENSITIVE_KEYS = {"api_key", "apikey", "token", "password", "secret",
                    "credential", "private_key", "access_key", "auth"}
def _sanitize_data(data):
    # 递归过滤 dict/list 中的敏感键值 → "[FILTERED]"
```

**P1-8 循环事件防护**：
```python
# publish() 中跳过同名回调（排除 lambda）
if (hasattr(callback, '__name__') and callback.__name__ != '<lambda>'
        and callback.__name__ == event.source):
    continue
```

### 11.5 main.py — P1-6：TASK_DECOMPOSED 事件

SOP 内化完成后发布事件：
```python
bus.publish(Event(
    event_type=EventType.TASK_DECOMPOSED,
    source="main",
    data={"task_id": task_id, "stage_count": N, "stages": [...]},
))
```
