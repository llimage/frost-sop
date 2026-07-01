# WorkBuddy 执行指令：家族资产运行链路修复（P1-Asset-Loop）

**版本**: P1-Asset-Loop  
**日期**: 2026-06-30  
**目标**: 修复家族资产体系的运行链路断裂，让武器库、记忆、复盘真正运转  
**预计耗时**: 3-4 小时  
**优先级**: P1（功能修复）

---

## 零、执行顺序

| 阶段 | 内容 | 预计耗时 | 验收标准 |
|------|------|---------|---------|
| **A1** | 数据库迁移：`skills` 表增加健康字段 | 30分钟 | 表结构正确 |
| **A2** | 修复 `record_usage()` 调用链路 | 90分钟 | 健康评分动态更新 |
| **A3** | 启用 `merge_from`（跨代际继承） | 60分钟 | 子辈产出合并到父辈 |
| **A4** | 扩展 `SkillExtractor` 失败复盘 | 60分钟 | 从失败日志提取教训 |
| **A5** | 验证修复（功能 + 测试） | 30分钟 | 资产体系可运行 |

---

## 一、数据库迁移：skills 表增加健康字段（A1）

**问题**: `skills` 表缺少 `health_score`, `usage_count`, `success_count`, `failure_count`, `last_used` 字段，`Armory` 的元数据无法持久化。

**文件**: `core/db.py`  
**位置**: `_migrate_skills_table` 方法（约第 433 行）

### 1.1 修改现有迁移方法

**old_string**:
```python
    def _migrate_skills_table(self, cursor):
        """F10: 为 skills 表添加 SkillExtractor 需要的列"""
        needed = {
            "trigger_keywords": "TEXT DEFAULT '[]'",
            "success_rate": "REAL DEFAULT 0.0",
            "status": "TEXT DEFAULT 'active'",
            "task_type": "TEXT DEFAULT ''",
        }
        existing = {col["name"] for col in cursor.execute("PRAGMA table_info(skills)").fetchall()}
        for col_name, col_def in needed.items():
            if col_name not in existing:
                try:
                    cursor.execute(f"ALTER TABLE skills ADD COLUMN {col_name} {col_def}")
                except Exception:
                    pass
```

**new_string**:
```python
    def _migrate_skills_table(self, cursor):
        """F10: 为 skills 表添加 SkillExtractor 需要的列 + V5.0 健康评分字段"""
        needed = {
            # F10 原有字段
            "trigger_keywords": "TEXT DEFAULT '[]'",
            "success_rate": "REAL DEFAULT 0.0",
            "status": "TEXT DEFAULT 'active'",
            "task_type": "TEXT DEFAULT ''",
            # V5.0 新增：武器库健康评分字段
            "health_score": "REAL DEFAULT 50.0",
            "usage_count": "INTEGER DEFAULT 0",
            "success_count": "INTEGER DEFAULT 0",
            "failure_count": "INTEGER DEFAULT 0",
            "avg_execution_time": "REAL DEFAULT NULL",
            "last_used": "TIMESTAMP DEFAULT NULL",
            "created_from": "TEXT DEFAULT 'manual'",
            "source": "TEXT DEFAULT ''",
            "confidence": "REAL DEFAULT 1.0",
        }
        existing = {col["name"] for col in cursor.execute("PRAGMA table_info(skills)").fetchall()}
        for col_name, col_def in needed.items():
            if col_name not in existing:
                # S-003 安全修复：验证列名
                if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', col_name):
                    continue
                if not re.match(r'^[A-Z]+\s*(DEFAULT\s+[^;\-]*|)$', col_def, re.IGNORECASE):
                    continue
                try:
                    cursor.execute(f"ALTER TABLE skills ADD COLUMN {col_name} {col_def}")
                except Exception:
                    pass
```

---

### 1.2 修改 `save` 方法以支持 skills 表完整字段

**文件**: `core/store.py`  
**位置**: `_save_to_sqlite` 方法（约第 80 行）

**old_string**（`skill_gene:` 分支）：
```python
            elif key.startswith("skill_gene:"):
                skill_id = f"skill_{key}"
                self._db.insert("skills", {
                    "id": skill_id,
                    "name": value.get("name", key),
                    "description": value.get("description", ""),
                    "skill_type": value.get("type", "functional"),
                    "content": json.dumps(value, ensure_ascii=False)
                })
```

**new_string**:
```python
            elif key.startswith("skill_gene:"):
                skill_id = f"skill_{key}"
                # V5.0: 支持武器库完整字段持久化
                self._db.insert("skills", {
                    "id": skill_id,
                    "name": value.get("name", key),
                    "description": value.get("description", ""),
                    "skill_type": value.get("type", "functional"),
                    "content": json.dumps(value, ensure_ascii=False),
                    # 健康评分字段（如果存在）
                    "health_score": value.get("health_score", 50.0),
                    "usage_count": value.get("usage_count", 0),
                    "success_count": value.get("success_count", 0),
                    "failure_count": value.get("failure_count", 0),
                    "avg_execution_time": value.get("avg_execution_time"),
                    "last_used": value.get("last_used"),
                    "created_from": value.get("created_from", "manual"),
                    "source": value.get("source", ""),
                    "confidence": value.get("confidence", 1.0),
                })
```

---

## 二、修复 `record_usage()` 调用链路（A2）

**问题**: `Armory.record_usage()` 是死代码，无任何调用方。武器库健康评分永远是 50.0。

**策略**: 在关键 Skill 执行完成后调用 `record_usage()`。选择三个最关键的 Skill：
1. `skills.llm:call_llm` — 每次 LLM 调用
2. `skills.orchestration:execute_stage` — 每次阶段执行
3. `skills.assemble:assemble` — 每次 Agent 组装

### 2.1 在 `skills/llm.py` 中记录 LLM 调用

**文件**: `skills/llm.py`  
**位置**: `call_llm` 函数末尾（成功/失败后）

先读文件确认 `call_llm` 的准确结构：

```python
# 假设 call_llm 返回 result dict，包含 _llm_response 等
```

**old_string**（假设 `call_llm` 的末尾返回前）：
```python
    return result
```

**new_string**:
```python
    # V5.0: 记录武器库使用情况
    try:
        from core.armory import get_armory_registry
        armory = get_armory_registry()
        weapon = armory.get("skill:call_llm")
        if weapon:
            success = result.get("_llm_response") is not None
            weapon.record_usage(
                success=success,
                execution_time=result.get("_execution_time")
            )
            armory._persist_to_store()
    except Exception:
        pass  # 武器库记录失败不影响主流程

    return result
```

---

### 2.2 在 `skills/orchestration.py` 中记录阶段执行

**文件**: `skills/orchestration.py`  
**位置**: `execute_stage` 函数末尾

先找到 `execute_stage` 的返回处。从之前阅读，它在约第 462 行调用 `_check_decision_point`。

```python
# 假设 execute_stage 的末尾有 return context
```

**old_string**（在 `execute_stage` 函数末尾的 `return` 前）：
```python
    return context
```

**new_string**:
```python
    # V5.0: 记录 orchestration 技能使用情况
    try:
        from core.armory import get_armory_registry
        armory = get_armory_registry()
        weapon = armory.get("skill:execute_stage")
        if not weapon:
            # 如果武器库中没有此技能，创建一个占位
            from core.armory import WeaponMetadata, WeaponType, WeaponCategory
            weapon = WeaponMetadata(
                id="skill:execute_stage",
                name="阶段执行器",
                type=WeaponType.SKILL,
                category=WeaponCategory.EXECUTION,
            )
            armory.register(weapon)
        
        stage_result = context.get("_stage_results", [])
        if stage_result:
            last_result = stage_result[-1]
            success = last_result.get("status") == "completed"
        else:
            success = True  # 无错误即成功
        
        weapon.record_usage(success=success)
        armory._persist_to_store()
    except Exception as e:
        logger.debug("武器库记录失败: %s", e)

    return context
```

---

### 2.3 在 `skills/assemble.py` 中记录 Agent 组装

**文件**: `skills/assemble.py`  
**位置**: `assemble` 或 `assemble_from_requirement` 函数末尾

**old_string**（假设在 `assemble` 函数返回前）：
```python
    return agent
```

**new_string**:
```python
    # V5.0: 记录组装技能使用情况
    try:
        from core.armory import get_armory_registry
        armory = get_armory_registry()
        weapon = armory.get("skill:assemble")
        if not weapon:
            from core.armory import WeaponMetadata, WeaponType, WeaponCategory
            weapon = WeaponMetadata(
                id="skill:assemble",
                name="Agent组装器",
                type=WeaponType.SKILL,
                category=WeaponCategory.EXECUTION,
            )
            armory.register(weapon)
        
        success = agent is not None
        weapon.record_usage(success=success)
        armory._persist_to_store()
    except Exception:
        pass

    return agent
```

---

### 2.4 修改 `ArmoryRegistry._persist_to_store` 以支持完整字段

**文件**: `core/armory.py`  
**位置**: `_persist_to_store` 方法（约第 330 行）

先确认当前实现：

```python
def _persist_to_store(self):
    if not self._store:
        return
    for weapon in self._weapons.values():
        self._store.save(f"skill:{weapon.id}", weapon.to_dict())
```

**old_string**:
```python
    def _persist_to_store(self):
        if not self._store:
            return
        for weapon in self._weapons.values():
            self._store.save(f"skill:{weapon.id}", weapon.to_dict())
```

**new_string**:
```python
    def _persist_to_store(self):
        if not self._store:
            return
        for weapon in self._weapons.values():
            data = weapon.to_dict()
            # V5.0: 确保健康评分字段被保存
            data.update({
                "health_score": weapon.health_score,
                "usage_count": weapon.usage_count,
                "success_count": weapon.success_count,
                "failure_count": weapon.failure_count,
                "avg_execution_time": weapon.avg_execution_time,
                "last_used": weapon.last_used,
            })
            self._store.save(f"skill:{weapon.id}", data)
            # 同时更新 skills 表（如果 DB 可用）
            try:
                from core.db import get_db
                db = get_db()
                existing = db.select_one("skills", "id", weapon.id)
                if existing:
                    db.update("skills", "id", weapon.id, {
                        "health_score": weapon.health_score,
                        "usage_count": weapon.usage_count,
                        "success_count": weapon.success_count,
                        "failure_count": weapon.failure_count,
                        "avg_execution_time": weapon.avg_execution_time,
                        "last_used": weapon.last_used,
                    })
            except Exception:
                pass  # DB 更新失败不影响内存状态
```

---

## 三、启用 `merge_from`（跨代际继承）（A3）

**问题**: `merge_from` 在 `skills/orchestration.py` 中定义，但从未被调用。子辈 Agent 完成后产出不合并回父辈。

### 3.1 在 `Agent` 类中添加 `destroy` 或 `cleanup` 方法

**文件**: `core/agent.py`  
**位置**: 在 `Agent` 类中添加方法

先确认 `Agent` 类是否有 `destroy` 方法。从之前阅读，它有 `__init__` 和 `run` 等。

**old_string**（在 `Agent` 类中查找 `destroy` 或 `__del__`）:

如果没有 `destroy` 方法，在类末尾添加：

```python
    # 如果没有 destroy 方法，在类末尾添加
```

**new_string**（在 `Agent` 类中合适位置插入）：
```python
    def destroy(self, context: dict = None):
        """
        V5.0: 销毁 Agent，将产出合并回父辈。
        
        Args:
            context: 可选的执行上下文，用于传递合并结果
        """
        # 1. 将子辈 store 合并到父辈
        if self._parent and self.store:
            from core.store import HierarchicalStore
            if isinstance(self._parent.store, HierarchicalStore):
                try:
                    self._parent.store.merge_from(
                        self.store,
                        filter_func=lambda key: key.startswith((
                            "output:", "lesson:", "_result", "artifact:", "memory:"
                        ))
                    )
                    if context:
                        context["_merged_to_parent"] = True
                except Exception as e:
                    if context:
                        context["_merge_error"] = str(e)
        
        # 2. 清理子辈资源
        self._status = "destroyed"
        
        # 3. 触发事件（如果 event_bus 可用）
        if self._event_bus:
            from core.event_bus import Event
            self._event_bus.publish(Event(
                event_type="agent.destroyed",
                source=f"agent:{self.agent_id}",
                data={"agent_id": self.agent_id, "parent_id": self._parent}
            ))
```

---

### 3.2 在 `orchestration.py` 中调用 `merge_from`

**文件**: `skills/orchestration.py`  
**位置**: `execute_stage` 或 `_persist_result` 中，当子辈 Agent 完成时

从之前阅读，`execute_stage` 在约第 462 行调用 `_check_decision_point`。

```python
# 在 execute_stage 中，当子辈执行完成后
```

**old_string**（假设在 `_execute_child` 或 `execute_stage` 中子辈完成后的逻辑）:

由于我不确定具体的调用位置，基于代码结构，在 `execute_stage` 返回前添加：

```python
    # 在 execute_stage 的合适位置（子辈执行完成后）
    # 假设 child_agent 执行完成后
```

**new_string**（在 `execute_stage` 中，当 `_execute_child` 返回后）:
```python
    # V5.0: 如果子辈 Agent 执行完成，调用 merge_from
    if "_child_agent" in context and context["_child_agent"]:
        child_agent = context["_child_agent"]
        if hasattr(child_agent, "destroy"):
            child_agent.destroy(context)
        else:
            # 回退：手动调用 merge_from
            try:
                from skills.orchestration import merge_from
                merge_from(context)
            except Exception as e:
                logger.warning("merge_from 失败: %s", e)
```

---

## 四、扩展 `SkillExtractor` 失败复盘（A4）

**问题**: `SkillExtractor` 只从成功日志提取技能，失败日志中的教训被丢弃。

### 4.1 添加失败模式扫描方法

**文件**: `core/skill_extractor.py`  
**位置**: 在 `SkillExtractor` 类中添加方法

**old_string**（在 `scan_successful_calls` 之后插入）：

```python
    # 在 scan_successful_calls 方法之后添加
```

**new_string**（在 `SkillExtractor` 类中，`scan_successful_calls` 之后）：
```python
    def scan_failure_patterns(self, limit: int = 100) -> List[Dict]:
        """
        V5.0: 扫描失败日志，提取失败模式。
        
        Args:
            limit: 最多扫描的文件数
            
        Returns:
            失败模式列表，每个模式包含失败类型、触发条件、规避策略
        """
        import os
        if not os.path.exists(self.tool_calls_dir):
            return []
        
        files = [f for f in os.listdir(self.tool_calls_dir) if f.endswith(".json")]
        failures = []
        
        for f in sorted(files, reverse=True)[:limit]:
            filepath = os.path.join(self.tool_calls_dir, f)
            try:
                with open(filepath, "r", encoding="utf-8") as fp:
                    data = json.load(fp)
            except (json.JSONDecodeError, IOError):
                continue
            
            # 只处理失败记录
            if not data.get("success") and data.get("error_info"):
                failures.append(data)
        
        return failures

    def extract_failure_pattern(self, failure: Dict) -> Optional[Dict]:
        """
        V5.0: 从单条失败记录提取失败模式。
        
        使用 LLM 分析失败原因，提取可复用的失败模式。
        """
        if not self._llm_client:
            return None
        
        prompt = f"""分析以下工具调用失败记录，提取可复用的失败模式：

工具名称: {failure.get('tool_name', 'unknown')}
参数: {json.dumps(failure.get('parameters', {}), ensure_ascii=False)}
错误信息: {failure.get('error_info', '')}
执行时间: {failure.get('execution_time', 'unknown')}

请输出以下 JSON 格式：
{{
    "pattern_type": "失败类型（如：参数错误、超时、权限不足、资源缺失）",
    "trigger": "什么情况下会触发这个失败",
    "avoidance": "如何避免这个失败",
    "confidence": 0.8,
    "severity": "low/medium/high"
}}
"""
        try:
            response = self._llm_client.complete(prompt)
            content = response.get("content", "")
            
            # 提取 JSON
            json_start = content.find("{")
            json_end = content.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                pattern = json.loads(content[json_start:json_end])
                pattern["source"] = failure.get("tool_name", "unknown")
                pattern["timestamp"] = failure.get("timestamp", "")
                return pattern
        except Exception:
            pass
        
        return None

    def save_failure_pattern(self, pattern: Dict) -> str:
        """
        V5.0: 将失败模式保存到武器库（作为 INTEL 类型资产）。
        """
        from core.armory import get_armory_registry, WeaponMetadata, WeaponType, WeaponCategory
        
        armory = get_armory_registry()
        pattern_id = f"intel:failure_pattern:{pattern['pattern_type']}:{pattern['source']}"
        
        weapon = WeaponMetadata(
            id=pattern_id,
            name=f"失败模式: {pattern['pattern_type']}",
            type=WeaponType.INTEL,
            category=WeaponCategory.IMMUN,
            description=pattern.get("avoidance", ""),
            tags=["failure_pattern", pattern.get("severity", "medium"), pattern.get("source", "")],
            confidence=pattern.get("confidence", 0.5),
            created_from="extracted",
        )
        armory.register(weapon)
        return pattern_id
```

---

### 4.2 添加失败复盘入口方法

**new_string**（在 `SkillExtractor` 类末尾添加）：
```python
    def run_failure_review(self, limit: int = 100) -> List[Dict]:
        """
        V5.0: 运行失败复盘，扫描失败日志并提取模式。
        
        Args:
            limit: 最多扫描的文件数
            
        Returns:
            提取的失败模式列表
        """
        failures = self.scan_failure_patterns(limit=limit)
        patterns = []
        
        for failure in failures:
            pattern = self.extract_failure_pattern(failure)
            if pattern and pattern.get("confidence", 0) > 0.6:
                self.save_failure_pattern(pattern)
                patterns.append(pattern)
        
        return patterns
```

---

## 五、验证修复（A5）

### 5.1 验证数据库迁移

```python
# 临时验证脚本
import sys
sys.path.insert(0, "/d/my_ai/Solo-Ops-Platform/workspace/frost-sop")
from core.db import get_db

db = get_db()
# 检查 skills 表是否有新字段
columns = db.execute_sql("PRAGMA table_info(skills)")
column_names = {c["name"] for c in columns}
required = {"health_score", "usage_count", "success_count", "failure_count", "last_used"}
missing = required - column_names
if missing:
    print(f"FAIL: 缺少字段: {missing}")
else:
    print("PASS: 所有健康评分字段已存在")
```

### 5.2 验证 `record_usage` 被调用

```python
# 临时验证脚本
import sys
sys.path.insert(0, "/d/my_ai/Solo-Ops-Platform/workspace/frost-sop")
from core.armory import get_armory_registry, WeaponMetadata, WeaponType, WeaponCategory

# 注册一个测试武器
armory = get_armory_registry()
weapon = WeaponMetadata(
    id="skill:test_usage",
    name="测试武器",
    type=WeaponType.SKILL,
    category=WeaponCategory.EXECUTION,
)
armory.register(weapon)

# 模拟使用
weapon.record_usage(success=True, execution_time=1.5)
print(f"usage_count: {weapon.usage_count}")
print(f"health_score: {weapon.health_score}")
assert weapon.usage_count == 1, "record_usage 未生效"
print("PASS: record_usage 工作正常")
```

### 5.3 验证 `merge_from`

```python
# 临时验证脚本
from core.store import Store, HierarchicalStore

parent_store = Store()
parent_store.save("test_key", "parent_value")
parent = HierarchicalStore(own_store=parent_store)

child_own = Store()
child_own.save("output:result", "child_result")
child = HierarchicalStore(own_store=child_own, parent=parent)

# 合并前
assert parent.load("output:result") is None

# 执行 merge_from（模拟 destroy）
parent.merge_from(child_own, filter_func=lambda k: k.startswith("output:"))

# 合并后
assert parent.load("output:result") == "child_result"
print("PASS: merge_from 工作正常")
```

### 5.4 验证失败复盘

```python
# 临时验证脚本
from core.skill_extractor import SkillExtractor

extractor = SkillExtractor()
# 如果没有失败日志，创建一条模拟的
import os, json
os.makedirs("data/tool_calls", exist_ok=True)
with open("data/tool_calls/fail_001.json", "w") as f:
    json.dump({
        "tool_name": "test_tool",
        "parameters": {"key": "value"},
        "success": False,
        "error_info": "连接超时",
        "timestamp": "2026-01-01T00:00:00"
    }, f)

failures = extractor.scan_failure_patterns(limit=10)
print(f"扫描到失败记录: {len(failures)}")
if failures:
    print("PASS: 失败复盘扫描工作正常")
else:
    print("INFO: 无失败日志可扫描")
```

---

## 六、验收清单

| # | 验收项 | 检查方法 | 通过标准 |
|---|--------|---------|---------|
| 1 | 数据库字段 | `PRAGMA table_info(skills)` | 有 `health_score` 等 6 个新字段 |
| 2 | `record_usage` 调用 | 运行上述验证脚本 | `usage_count >= 1` |
| 3 | `merge_from` 启用 | 运行上述验证脚本 | 子辈产出合并到父辈 |
| 4 | 失败复盘 | 运行上述验证脚本 | 扫描到失败记录 |
| 5 | 武器库持久化 | 检查 `data/assets.json` | 有 `health_score` 字段 |
| 6 | 无新增错误 | 启动 API 测试 | 无异常 |

---

## 七、关键注意事项

1. **修改顺序**: 先数据库迁移（A1），再 `record_usage`（A2），再 `merge_from`（A3），再失败复盘（A4）
2. **向后兼容**: `record_usage` 的调用用 `try/except` 包裹，武器库失败不影响主流程
3. **数据库已有数据**: 迁移使用 `ALTER TABLE ADD COLUMN`，已有数据会自动获得默认值
4. **性能影响**: `_persist_to_store` 每次调用都写入 SQLite，如果调用频繁可考虑批量写入
5. **测试覆盖**: 如果现有测试使用了非法表名/列名，白名单验证会导致测试失败。这是预期行为，需要修复测试

---

*指令结束。按顺序执行，每阶段完成后运行对应验收项。*
