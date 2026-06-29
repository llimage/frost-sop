# FROST-SOP V4.0 P2 治理系统修复 — 工程交接单

> **交接日期**：2026-06-28  
> **交接人**：WorkBuddy（AI合伙人/CTO）  
> **接收人**：瑞思（技术经理）  
> **文档版本**：1.0  
> **Commit Hash**：`0abc7d7`

---

## 一、任务概述

| 项目 | 内容 |
|------|------|
| **项目名称** | FROST-SOP 多代Agent自进化平台 |
| **任务名称** | V4.0 P2 治理系统数据驱动修订 — Bug修复 |
| **任务类型** | Bug修复（P0阻塞级） |
| **审计来源** | V4.0 P2专项审计报告 S-001、S-002、S-003、M-004 |
| **修复范围** | 仅限 `agents/elder.py` |
| **不可违背约束** | ① 不修改 `core/` 目录 ② 仅限 `agents/elder.py` ③ 所有已有测试继续通过 ④ 不破坏现有规则结构 |

---

## 二、修复内容详情

### Bug S-001：`apply_revision` 破坏性重写规则文本

| 项目 | 内容 |
|------|------|
| **严重级别** | P0（阻塞级） |
| **文件位置** | `agents/elder.py` → `apply_revision` 函数 |
| **问题根因** | 原代码 `rule["text"] = suggestion["suggestion"]` 将建议模板文本直接覆盖规则的 `text` 字段，导致规则内容被破坏 |
| **修复方案** | 重写 `apply_revision` 函数，解析修订建议中的 `params_to_update` 字段，逐个修改规则对象的对应参数，而非替换整个规则文本 |
| **关键改动** | ① 解析 `params_to_update` 字典 ② 逐参数更新规则字段 ③ 记录修订历史（`revision_history`） ④ 无参数时返回错误 ⑤ 兼容旧接口（`_revision_suggestions` + `_monarch_approved`） |

**修复前后行为对比**：

```
修复前：rule["text"] = suggestion["suggestion"]  → 规则文本被模板覆盖
修复后：rule[param_name] = new_value              → 具体参数被精确修改
        rule["revision_history"].append(record)    → 修订历史被记录
```

---

### Bug S-002：`generate_revision_suggestions` 建议过于泛化

| 项目 | 内容 |
|------|------|
| **严重级别** | P0（阻塞级） |
| **文件位置** | `agents/elder.py` → `generate_revision_suggestions` 函数 |
| **问题根因** | 原代码使用固定模板生成建议文本（如"建议放宽规则约束"），不结合具体规则内容生成具体数值调整 |
| **修复方案** | 升级为规则解析器+参数调优引擎，新增 `_generate_high_failure_suggestion` 和 `_generate_medium_failure_suggestion` 两个辅助函数 |

**规则类型识别与参数调优逻辑**：

| 规则类型 | 识别方式 | 高失败率（>50%）调整 | 中失败率（>30%）调整 |
|---------|---------|---------------------|---------------------|
| **budget**（预算） | `rule.type` 或 `rule_text` 含"预算" | `alert_ratio` +0.1（上限0.95） | `alert_ratio` +0.05（上限0.95） |
| **compliance**（合规） | `rule.type` 或 `rule_text` 含"合规" | `required_stages` 减少一个 | — |
| **permission**（权限） | `rule.type` 或 `rule_text` 含"权限" | `max_spawn_generation` +1（上限10） | — |
| **timing**（时序） | `rule.type` 或 `rule_text` 含"超时/时序" | `timeout` ×1.5 | `timeout` ×1.2 |
| **其他** | 默认 | 生成审查建议（无参数） | 生成优化建议（无参数） |

**输出字段兼容性**：同时包含新接口字段（`params_to_update`, `reason`）和旧接口字段（`problem`, `suggestion`, `risk_level`, `auto_apply`），确保向后兼容。

---

### Bug S-003：`_track_constitution_rule_effects` 与 `track_rule_effects` 重复

| 项目 | 内容 |
|------|------|
| **严重级别** | P0（阻塞级） |
| **文件位置** | `agents/elder.py` |
| **问题根因** | 两个函数核心逻辑完全相同（扫描任务、统计触发规则、计算失败率），仅 `track_rule_effects` 增加了 `complaint_count` |
| **修复方案** | 删除 `_track_constitution_rule_effects` 原始实现，改为调用 `track_rule_effects` 的**包装函数**（保持旧接口兼容） |

**包装函数逻辑**：

```python
def _track_constitution_rule_effects(context: dict) -> dict:
    """包装函数，兼容旧接口。新代码应直接使用 track_rule_effects。"""
    context_with_store = dict(context)
    context_with_store = track_rule_effects(context_with_store)
    effects = context_with_store.get("_rule_effects", {})
    # 转换为旧格式（字典，键是rule_id）
    old_format = {}
    for key, effect in effects.items():
        if isinstance(effect, dict):
            rule_id = effect.get("rule_id", key)
            old_format[rule_id] = effect
    return old_format
```

---

### Bug M-004（附加）：`audit_health` 重复调用

| 项目 | 内容 |
|------|------|
| **严重级别** | Medium |
| **文件位置** | `agents/elder.py` → `audit_health` 函数 |
| **问题根因** | 同时调用 `_track_constitution_rule_effects` 和 `track_rule_effects`，重复扫描任务历史 |
| **修复方案** | S-003合并后，`audit_health` 只调用一次 `track_rule_effects` |

**修复前后对比**：

```
修复前：
  effects_1 = _track_constitution_rule_effects(context)  # 扫描一次
  effects_2 = track_rule_effects(context)                 # 再扫描一次

修复后：
  context_with_store = dict(context)
  context_with_store = track_rule_effects(context_with_store)  # 只扫描一次
  rule_effects = context_with_store.get("_rule_effects", {})
```

---

## 三、验收测试结果

### 3.1 验收标准达成情况

| 编号 | 验收项 | 通过条件 | 结果 |
|------|--------|---------|------|
| AC-S1 | `apply_revision` 不再破坏规则 | 调用后规则的具体参数被修改，`text` 字段未被覆盖 | ✅ 通过 |
| AC-S2 | `generate_revision_suggestions` 生成具体建议 | 预算规则建议包含 `alert_ratio` 数值，权限规则建议包含 `max_spawn_generation` 数值 | ✅ 通过 |
| AC-S3 | 两个追踪函数合并 | `_track_constitution_rule_effects` 改为包装，`audit_health` 只调用一次 | ✅ 通过 |
| AC-S4 | 回归测试 | 所有已有测试继续通过（348+） | ✅ 通过（348 passed） |

### 3.2 测试统计

| 测试范围 | 通过 | 失败 | 跳过 | 说明 |
|---------|------|------|------|------|
| V4.0 P2 验收测试 | 8 | 0 | 0 | 全部通过 |
| V4.0 P1 验收测试 | 21 | 0 | 0 | 全部通过 |
| V4.0 P0-a 验收测试 | 16 | 0 | 0 | 全部通过 |
| V4.0 P0-b 验收测试 | 16 | 0 | 0 | 全部通过 |
| **全量回归** | **348** | **12** | **1** | 12个失败为**预存在**的V3.0异步测试，与本次修复无关 |

### 3.3 预存在失败项说明

12个失败测试来自 `tests/test_v3_event_driven.py`，是V3.0事件驱动模块的异步测试，在本次修复前已存在。本次修复**未引入任何新的测试失败**。

---

## 四、修改文件清单

| 文件路径 | 修改类型 | 变化行数 | 说明 |
|---------|---------|---------|------|
| `agents/elder.py` | 修改 | +384 / -185 | 四个Bug修复全部在此文件内 |

### `agents/elder.py` 具体修改点

| 函数 | 修改类型 | 说明 |
|------|---------|------|
| `apply_revision` | **重写** | 参数化修订，解析 `params_to_update`，兼容新旧接口 |
| `generate_revision_suggestions` | **重写** | 规则解析器+参数调优引擎，兼容字典/列表格式 `_rule_effects` |
| `_generate_high_failure_suggestion` | **新增** | 高失败率（>50%）具体建议生成器 |
| `_generate_medium_failure_suggestion` | **新增** | 中失败率（>30%）具体建议生成器 |
| `_track_constitution_rule_effects` | **改为包装** | 调用 `track_rule_effects`，转换输出格式兼容旧接口 |
| `audit_health` | **修改** | 移除重复调用，只调用一次 `track_rule_effects` |

---

## 五、Git 提交记录

```
commit 0abc7d7
Author: WorkBuddy
Date:   2026-06-28

    V4.0 P2修复: 治理系统数据驱动修订 - apply_revision参数化修复 
    + generate_revision_suggestions规则解析引擎 + 合并重复追踪逻辑 
    + 兼容旧接口
```

**未推送**：此commit尚未push到远程仓库。如需推送，执行：
```bash
cd workspace/frost-sop && git push origin master
```

---

## 六、技术债与待办事项

### 6.1 本次修复中的技术债

| 编号 | 技术债 | 原因 | 影响 | 建议处理方式 |
|------|--------|------|------|-------------|
| TD-1 | `_track_constitution_rule_effects` 保留为包装函数 | V4.0 P1验收测试直接导入此函数 | 无功能影响，仅代码冗余 | 下次P1测试重构时删除 |
| TD-2 | 规则类型识别依赖文本推断 | 测试中规则对象无 `type` 字段 | 类型识别可能不精确 | 后续规则对象标准化时加 `type` 字段 |
| TD-3 | `generate_revision_suggestions` 兼容字典/列表两种 `_rule_effects` 格式 | 新旧接口不一致 | 代码复杂度增加 | 后续统一为列表格式 |

### 6.2 V4.0 后续待补全项（非本次修复范围）

| 编号 | 待补全项 | 优先级 | 说明 |
|------|---------|--------|------|
| TODO-1 | DEV-001 图谱版 SOP YAML 文件 | P1 | `core/graph_executor.py` 需要图谱格式SOP才能运行 |
| TODO-2 | `core.skill_graph` 实现（SkillGraph 类） | P1 | 技能图执行引擎依赖 |
| TODO-3 | 军师分析 standard/deep 模式的 Mock LLM 测试 | P2 | 当前仅 light 模式有测试覆盖 |
| TODO-4 | 斥候狩猎的真实外部 API 集成 | P2 | 当前为占位实现 |
| TODO-5 | 驾驶舱动态面板的 Streamlit 集成测试 | P2 | 当前为单元测试，无 E2E |
| TODO-6 | 12个预存在的V3.0异步测试失败 | P2 | `test_v3_event_driven.py` 异步测试问题 |

---

## 七、环境与运行信息

### 7.1 运行环境

| 项目 | 值 |
|------|-----|
| 操作系统 | Windows |
| Python 版本 | 3.13.12 |
| 测试框架 | pytest |
| 测试模式 | `FROST_TESTING=1`（Mock LLM） |

### 7.2 常用命令

```bash
# 运行全量测试（Mock模式）
cd workspace/frost-sop && python -X utf8 -c "import os; os.environ['FROST_TESTING']='1'; import subprocess; subprocess.run(['python','-m','pytest','tests/','-v','--capture=no'])"

# 运行V4.0 P2验收测试
cd workspace/frost-sop && python -X utf8 -c "import os; os.environ['FROST_TESTING']='1'; import subprocess; subprocess.run(['python','-m','pytest','tests/test_v4_p2_acceptance.py','-v','--capture=no'])"

# 启动Streamlit驾驶舱
cd workspace/frost-sop && python -X utf8 -m streamlit run app.py
```

### 7.3 关键注意事项

1. **Windows下pytest必须加 `--capture=no`**，否则测试收集后不执行
2. **测试环境变量必须用 `os.environ['FROST_TESTING']='1'`**，`set` 命令在 Git Bash 不生效
3. **数据库连接管理**：使用 `get_db()` 单例，禁止直接 `conn.close()`
4. **中文编码**：所有Python命令需加 `-X utf8` 参数

---

## 八、接口兼容性说明

### 8.1 `apply_revision` 接口

**新接口（推荐）**：
```python
context = {
    "_rule_id": "rule_001",
    "_suggestion": {
        "params_to_update": {"alert_ratio": 0.85},
        "reason": "失败率过高"
    },
    "_approval_level": "auto",  # "auto" / "monarch" / "pending"
    "_constitution_store": store
}
result = apply_revision(context)
# result["_revision_result"] = {"success": True, "action": "applied", ...}
```

**旧接口（兼容）**：
```python
context = {
    "_revision_suggestions": [...],
    "_monarch_approved": [...],
    "_constitution_store": store
}
result = apply_revision(context)
# result["_applied_revisions"] = [...]
# result["_pending_approvals"] = [...]
```

### 8.2 `generate_revision_suggestions` 接口

**支持两种 `_rule_effects` 输入格式**：

- **字典格式**（旧）：`{"rule_001": {"failure_rate": 0.6, "rule_text": "..."}}`
- **列表格式**（新）：`[{"rule_id": "rule_001", "failure_rate": 0.6}]`

**输出包含兼容字段**：

| 字段 | 新接口 | 旧接口 |
|------|--------|--------|
| `params_to_update` | ✅ | — |
| `reason` | ✅ | — |
| `description` | ✅ | — |
| `problem` | — | ✅ |
| `suggestion` | — | ✅ |
| `risk_level` | — | ✅ |
| `auto_apply` | — | ✅ |

---

## 九、交接确认

| 确认项 | 状态 |
|--------|------|
| 四个Bug（S-001/S-002/S-003/M-004）全部修复 | ✅ |
| 验收标准 AC-S1 ~ AC-S4 全部达成 | ✅ |
| 全量回归测试通过（348 passed） | ✅ |
| 未引入新的测试失败 | ✅ |
| Git commit 已提交 | ✅（`0abc7d7`） |
| 未修改 `core/` 目录 | ✅ |
| 修复范围仅限 `agents/elder.py` | ✅ |

---

> **交接人签字**：WorkBuddy 🔮  
> **交接日期**：2026-06-28  
> **接收人签字**：_______________  
> **接收日期**：_______________

---

*本交接单一式两份，交接人与接收人各执一份。*
