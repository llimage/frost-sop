# FROST-SOP V4.0 P2 代码级审计报告

**审计日期**: 2026-06-28
**审计版本**: `603e0eb`（V4.0 P2: 治理系统数据驱动修订）
**审计范围**: `agents/elder.py`（新增治理系统）+ `tests/test_v4_p2_acceptance.py`（验收测试）
**审计方法**: 逐行代码审查 + 测试静态分析 + 声称验证
**审计原则**: 颗粒度最低、最严苛、诚实、中肯

---

## 一、总体结论

**评级**: ⚠️ **有条件通过（Conditional Pass）**

治理系统的**框架已搭建**（规则追踪、建议生成、分级应用），但核心功能"数据驱动修订"存在**严重语义错误**——建议文本被直接写入规则文本，生成的建议内容过于泛化，无法被实际执行。这不是真正的"数据驱动修订引擎"，而是"规则效果报告生成器"。

| 维度 | 评分 | 说明 |
|------|------|------|
| 功能完整性 | ⚠️ | 框架完整，但核心逻辑有严重缺陷 |
| 代码质量 | ⚠️ | 重复代码、未验证的修改、方向漂移检测过于简单 |
| 测试覆盖 | ✅ | 8个测试覆盖主要路径，但深度不足 |
| 架构一致性 | ⚠️ | 与白皮书"数据驱动修订"定义有偏差 |
| 全量回归声称 | ❌ | 348 passed 无法验证，与之前审计发现一致 |

---

## 二、严重问题（阻塞级）

### 🔴 S-001: `apply_revision` 将建议文本直接写入规则文本（语义错误）

**位置**: `agents/elder.py:657`

**代码**:
```python
rule["text"] = suggestion["suggestion"]
```

**问题**: `suggestion["suggestion"]` 的值是 `generate_revision_suggestions` 生成的建议文本，例如：
- "建议放宽规则约束，或拆分为多个子规则"（high risk）
- "建议优化规则表述，减少歧义"（medium risk）
- "建议收集用户反馈，调整规则优先级"（complaint rate 高时）

这些**建议文本**被直接写入规则的 `text` 字段，成为了**规则的正式文本**。这意味着：
- 规则从"预算预警比例 80%"变成了"建议优化规则表述，减少歧义"
- 规则从"合规检查必须执行"变成了"建议放宽规则约束，或拆分为多个子规则"

**建议 ≠ 修订后的规则**。建议文本是**人类可读的说明**，规则文本是**机器可执行的约束**。两者不能互换。

**影响**: 如果此代码在生产环境运行，宪法规则会被破坏性重写，导致后续所有任务因规则格式无效而失败。

**修复建议**:
1. `generate_revision_suggestions` 应生成**具体的修订参数**，而非建议文本：
   ```python
   {
       "rule_id": "rule_001",
       "target_param": "budget_alert_ratio",  # 具体参数名
       "old_value": 0.8,
       "new_value": 0.85,  # 具体数值
       "reason": "失败率 40%",
   }
   ```
2. `apply_revision` 应解析修订参数，修改具体字段，而非直接替换整个规则文本。

---

### 🔴 S-002: `generate_revision_suggestions` 生成的建议过于泛化，无具体修订方案

**位置**: `agents/elder.py:568-605`

**代码**:
```python
if effect["failure_rate"] > 0.5:
    suggestion = f"建议放宽规则约束，或拆分为多个子规则"
elif effect["failure_rate"] > 0.3:
    suggestion = f"建议优化规则表述，减少歧义"
```

**问题**: 建议文本是**固定模板**，完全不结合具体规则内容。例如：
- 对于规则"预算预警比例 80%"（失败率40%），建议文本是"建议优化规则表述，减少歧义"
- 但真正的修订应该是"将预算预警比例从80%调整为85%"
- 对于规则"最大代际限制为3"（失败率50%），建议文本是"建议放宽规则约束，或拆分为多个子规则"
- 但真正的修订应该是"将最大代际限制从3调整为5"

**白皮书要求**: "数据驱动修订"——规则效果数据驱动**具体参数的调整**。

**当前实现**: 规则效果数据驱动**固定模板文本的输出**。

**修复建议**: 引入规则解析器（Rule Parser），从规则文本中提取参数，根据效果数据计算调整方向：
- 预算预警比例（数字）→ 根据失败率计算新比例
- 代际限制（整数）→ 根据失败率计算新限制
- 合规检查列表（字符串数组）→ 根据失败项移除/新增

---

### 🔴 S-003: `_track_constitution_rule_effects` 与 `track_rule_effects` 重复代码

**位置**: `agents/elder.py:381-429`（`_track_constitution_rule_effects`）和 `436-534`（`track_rule_effects`）

**问题**: 两个函数有几乎相同的逻辑：
- 都读取 `constitution_store.load("constitution:rules")`
- 都扫描 `asset_store` 中 `task:` 键
- 都统计 `triggered_rules` 的成功/失败次数
- 都计算 `failure_rate`

`track_rule_effects` 在 `_track_constitution_rule_effects` 之上增加了 `complaint_count` 和 `rules_need_revision`，但核心统计逻辑完全重复。

`audit_health`（第332行）调用了 `_track_constitution_rule_effects`，但 `track_rule_effects` 是单独的公共函数。如果两者被同时调用，会重复扫描整个任务历史，性能浪费。

**修复建议**: 将 `_track_constitution_rule_effects` 作为 `track_rule_effects` 的内部实现，或让 `track_rule_effects` 直接调用 `_track_constitution_rule_effects` 并扩展 complaint 统计。

---

## 三、中等问题

### ⚠️ M-001: 方向漂移检测过于简单，误报率高

**位置**: `agents/elder.py:350-378`

**代码**:
```python
def _detect_direction_drift(context: dict) -> bool:
    # 读取最近3次军师分析简报
    briefings = [...]
    if len(briefings) < 3:
        return False
    recent = briefings[-3:]
    topics = [b.get("main_topic", "") for b in recent]
    if len(set(topics)) == 3:
        return True
    return False
```

**问题**:
1. **逻辑缺陷**: 如果3次简报的主题分别是"财务"、"运营"、"财务"，`set` 去重后是2个，判定为无漂移。但如果主题是"财务A"、"财务B"、"财务C"（都是财务但不同子主题），`set` 去重后是3个，判定为漂移。这种判定标准过于粗糙。
2. **数据缺失**: 当前代码中没有其他代码创建 `briefing:` 键。`briefings` 列表几乎总是空的，因此 `len(briefings) < 3` 几乎总是成立，函数永远返回 `False`。
3. **白皮书定义**: 方向漂移是"军师分析方向是否与家族战略方向一致"，不是"简报主题是否重复"。

**修复建议**:
1. 定义"战略方向"的基准（如君主设定的年度目标）
2. 将简报中的建议与战略方向对比，计算偏离度
3. 偏离度超过阈值时判定为漂移

---

### ⚠️ M-002: 测试未验证 Store 中的实际修改

**位置**: `tests/test_v4_p2_acceptance.py:187-301`

**问题**: `test_apply_revision_auto` 和 `test_apply_revision_monarch_approved` 使用了 `MagicMock` 作为 `constitution_store`，但：
- 没有验证 `constitution_store.save()` 的调用参数
- 没有验证 `constitution_store.load()` 的调用次数
- 没有验证规则文本是否真的被修改

例如，在 `test_apply_revision_auto` 中：
```python
mock_constitution_store = MagicMock()
mock_constitution_store.load.return_value = [
    {"id": "rule_001", "text": "预算预警比例 80%"},
]
```

测试验证了 `applied[0]["applied_by"] == "auto"`，但没有验证 `save` 是否被调用、调用时的参数是什么。如果 `apply_revision` 中第667行 `break` 没有执行（因为循环中没有匹配到规则），测试仍然通过。

**修复建议**: 在测试中使用 `assert_called_with` 验证 `save` 的调用参数，或验证 `load` 后的 `text` 字段确实被修改了。

---

### ⚠️ M-003: 全量测试声称（348 passed）无法独立验证

**声称**: "348 passed / 12 failed / 1 error"

**问题**: 与之前审计一致，全量测试运行存在环境问题：
- 全项目共 56 个测试文件、364 个 test_ 函数
- 声称 348 passed 意味着 95.6% 的测试通过
- 但之前审计发现 pytest 全量运行有 `I/O operation on closed file` 错误
- 12 failed + 1 error 的来源无法验证（是否为预存问题？）

**建议**: 提供可复现的测试命令和完整输出，或修正为实际可运行的数字。

---

### ⚠️ M-004: `audit_health` 重复调用 `track_rule_effects`

**位置**: `agents/elder.py:332-335`

**代码**:
```python
if check_type in ("rule_effect", "full"):
    rule_effects = _track_constitution_rule_effects(context)
    health_report["rule_effects"] = rule_effects
    context["_rule_effects"] = rule_effects
```

**问题**: `audit_health` 调用了 `_track_constitution_rule_effects`，但如果用户后续调用 `track_rule_effects`，它会重新扫描整个任务历史（第二次扫描），`context["_rule_effects"]` 被覆盖。

虽然这不是错误，但存在性能浪费和潜在不一致风险。`audit_health` 应该直接调用 `track_rule_effects`（公共接口），而不是内部实现 `_track_constitution_rule_effects`。

---

## 四、轻微问题

### ℹ️ L-001: `audit_health` 检查类型命名不一致

**位置**: `agents/elder.py:290`

`check_type` 的取值：
- `"routine"`（常规）
- `"drift"`（方向漂移）
- `"rule_effect"`（规则效果）
- `"full"`（完整）

但 `generate_revision_suggestions` 的 docstring 中 `risk_level` 取值为 `"low" | "medium" | "high"`。两者命名不一致，但属于不同领域，可以接受。

### ℹ️ L-002: 日志消息中英文混杂

**位置**: `agents/elder.py:530, 669, 691`

```python
logger.warning("[Governance] 持久化规则效果失败: %s", e)
logger.warning("[Governance] 应用规则修订失败: %s", e)
```

建议统一为英文日志，或使用中文前缀，保持日志格式一致性。

---

## 五、诚实的进度重估

### V4.0 P2 声称 vs 实际

| AC | 声称 | 实际验证 | 状态 |
|----|------|----------|------|
| AC-9: 治理系统 | 规则追踪+修订建议+分级权限 | ✅ 框架存在，但建议质量低，修订应用有语义错误 | 部分完成 |
| 测试覆盖 | 8个测试全部通过 | ✅ 8个测试存在且通过，但深度不足 | 部分完成 |
| 全量回归 | 348 passed / 12 failed | ❌ 无法独立验证 | 无法验证 |
| 新增文件 | `agents/elder.py` + `tests/test_v4_p2_acceptance.py` | ✅ 2个文件，+646行 | 完成 |

### V4.0 P2 新增代码质量

| 函数 | 行数 | 复杂度 | 问题 |
|------|------|--------|------|
| `audit_health` | 76 | 中等 | 检查类型分支+方向漂移+规则效果 |
| `_detect_direction_drift` | 29 | 低 | 逻辑过于简单 |
| `_track_constitution_rule_effects` | 49 | 中等 | 与 `track_rule_effects` 重复 |
| `track_rule_effects` | 99 | 中等 | 与 `_track_constitution_rule_effects` 重复 |
| `generate_revision_suggestions` | 79 | 低 | 建议模板化，无具体方案 |
| `apply_revision` | 88 | 中等 | 建议文本直接写入规则文本（S-001） |
| **总计** | **420** | — | **3个严重+4个中等** |

---

## 六、建议修复优先级

### 第一优先级（下次迭代前）
1. **修复 S-001**: `apply_revision` 不应将建议文本直接写入规则文本。需要设计规则解析器，从规则中提取参数，生成具体修订参数。
2. **修复 S-002**: `generate_revision_suggestions` 需要生成具体的修订方案（参数+数值），而非模板化的建议文本。
3. **修复 S-003**: 合并 `_track_constitution_rule_effects` 和 `track_rule_effects` 的重复逻辑。

### 第二优先级
4. **修复 M-001**: 重新设计方向漂移检测，使用语义相似度而非简单主题对比。
5. **修复 M-002**: 补充测试验证 Store 修改（`assert_called_with`）。
6. **修正 M-003**: 提供可复现的全量测试命令和输出。

### 第三优先级
7. **修复 M-004**: `audit_health` 调用 `track_rule_effects` 而非 `_track_constitution_rule_effects`。

---

## 七、审计文件索引

| 文件 | 审计内容 | 新增行数 | 关键问题 |
|------|---------|---------|---------|
| `agents/elder.py` | 治理系统（6个新函数） | +284 | S-001, S-002, S-003 |
| `tests/test_v4_p2_acceptance.py` | 验收测试（8个） | +362 | M-002 |

---

## 八、总体评价

V4.0 P2 的治理系统框架已经搭建，三个核心函数（`track_rule_effects`、`generate_revision_suggestions`、`apply_revision`）都有清晰的职责边界和输入输出契约。测试覆盖了主要路径，分级修订权限的逻辑设计正确。

但**"数据驱动修订"的核心功能**——根据效果数据生成具体的、可执行的修订方案——尚未实现。当前建议文本是模板化的，无法被实际应用。`apply_revision` 将建议文本直接写入规则文本的做法是一个严重的语义错误，如果运行在生产环境，会损坏宪法规则。

**建议**: 在下一迭代中，将 `generate_revision_suggestions` 升级为**规则解析器+参数调优引擎**，结合 LLM 或规则模板，根据规则类型和效果数据生成具体的参数调整方案。`apply_revision` 应解析这些参数，修改具体字段，而非替换整个规则文本。

---

*审计完成。V4.0 P2 的治理系统框架是扎实的，但核心功能需要重大改进。*
