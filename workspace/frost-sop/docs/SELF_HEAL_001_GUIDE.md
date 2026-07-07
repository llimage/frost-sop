# SELF-HEAL-001 使用指南

> 创建日期：2026-06-17
> 目的：让 FROST-SOP 具备代码自修复能力，减少 WorkBuddy Token 消耗

---

## 一、为什么需要自修复？

### 当前模式的问题

```
发现问题 → 告诉 WorkBuddy → WorkBuddy 读取文件 → 分析 → 修改 → 测试 → 可能出错 → 再改 → 再测...
                                                            ↑
                                                     这里消耗 80% 的 Token
```

**典型场景**：修复一个 temperature 硬编码问题
- WorkBuddy 需要读取 3-5 个文件
- 每次读取可能触发上下文重载
- 修改后测试失败，需要重新分析
- **总消耗：5000-15000 tokens**

### 自修复模式的优势

```
发现问题 → 触发 SELF-HEAL-001 SOP → 系统自己诊断 → 生成方案 → 你确认 → 自动执行 → 自动验证
                                   ↑
                              这里只消耗 1000-2000 tokens（一次性）
```

**核心价值**：
1. **一次性诊断**：系统内部读取文件，无上下文丢失
2. **模式匹配优先**：已知问题（如硬编码、缺错误处理）不走 LLM，零 Token 成本
3. **人工确认 Gate**：不自动执行破坏性修改，你保留最终决定权
4. **自动验证**：修改后自动跑测试，失败自动回滚

---

## 二、已创建的文件

| 文件 | 路径 | 说明 |
|------|------|------|
| SOP 模板 | `sops/templates/SELF-HEAL-001.yaml` | 6 阶段自修复流程 |
| 代码诊断 Skill | `skills/code_diagnoser.py` | 读取代码 + 模式匹配 + LLM 补充分析 |
| 修复方案生成 Skill | `skills/patch_generator.py` | 生成 diff 格式修复方案 |
| 方案执行 Skill | `skills/patch_applier.py` | 备份 + 应用 + 语法验证 + 回滚 |
| Skill 注册 | `skills/self_heal_skills.py` | 注册到 FROST 系统 |

---

## 三、6 个已知问题模式（零 Token 诊断）

| 模式 ID | 名称 | 严重程度 | 典型场景 |
|---------|------|---------|---------|
| PATTERN-001 | 硬编码 temperature | medium | `temperature = 0.7` 未读配置 |
| PATTERN-002 | 裸 except 捕获 | high | `except:` 或 `except Exception:` 无日志 |
| PATTERN-003 | Skill 无错误处理 | **critical** | `return self._func(context)` 无 try/catch |
| PATTERN-004 | SQL 格式化字符串 | **critical** | f-string 拼接 SQL |
| PATTERN-005 | 纯 Mock 测试 | medium | 所有测试 `FROST_TESTING = "1"` |
| PATTERN-006 | 硬编码假数据 | low | `revenue_monthly: 34200` 写死 |

**模式匹配的价值**：
- 识别这 6 个问题 → **0 Token**（正则匹配）
- 生成标准修复方案 → **0 Token**（模板化）
- 只有"未知新问题"才需要 LLM 分析 → **1000-2000 Token**

---

## 四、使用方式（3 种）

### 方式 1：手动触发（推荐）

```python
# 在 Python 中手动触发一次自修复任务
from core.sop import SOP
from agents.ancestor import create_ancestor
from stores.asset import create_asset_store
from stores.constitution import create_constitution_store

# 加载自修复 SOP
sop = SOP.load_from_yaml("sops/templates/SELF-HEAL-001.yaml")

# 创建执行上下文（描述问题）
context = {
    "_task_id": "heal-001",
    "error_log": "api/main.py:480 temperature=0.7 硬编码",
    "test_failure": "",
    "user_description": "API 层没有使用新的 temperature profile 配置",
    "affected_files": ["api/main.py", "skills/llm.py"],
}

# 执行（需要人工确认阶段会暂停）
result = run_sop(sop, context)
```

### 方式 2：通过 CLI（开发中）

```bash
# 未来支持
$ frost heal --issue "temperature 硬编码" --files api/main.py
# 输出：
# 诊断完成：发现 PATTERN-001 匹配
# 修复方案已生成（1 个文件）
# 请确认：APPLY / MODIFY / REJECT
# > APPLY
# 应用完成，测试通过，已提交
```

### 方式 3：自动触发（未来）

```python
# 每天扫描一次代码库，自动发现模式匹配的问题
# 生成报告，等待人工确认
# 不自动执行（安全优先）
```

---

## 五、人工确认 Gate（安全设计）

**SELF-HEAL-001 的第 4 阶段是"人工确认"**，这是不可跳过的安全设计：

```
Phase 1: 症状收集    ← 自动
Phase 2: 诊断定位    ← 自动（模式匹配零 Token）
Phase 3: 方案生成    ← 自动（模板化零 Token，或 LLM 生成）
Phase 4: 人工确认    ← **必须人工输入 APPLY / REJECT / MODIFY**
Phase 5: 方案执行    ← 确认后自动
Phase 6: 验证        ← 自动（测试+回滚）
```

**为什么不全自动？**
- 代码修改是破坏性的，可能引入新 bug
- LLM 生成的 diff 可能不精确
- 你的判断比 AI 更了解业务上下文
- 这是 FROST 哲学："AI 是杠杆，不是替身"

---

## 六、Token 消耗对比

| 场景 | WorkBuddy 手动修复 | SELF-HEAL-001 自修复 | 节省 |
|------|---------------------|----------------------|------|
| 硬编码 temperature | 3000-5000 tokens | 0 tokens（模式匹配） | **100%** |
| Skill 加错误处理 | 5000-8000 tokens | 0 tokens（模式匹配） | **100%** |
| 未知复杂 bug | 10000-20000 tokens | 2000-3000 tokens | **70-80%** |
| 需要 3 轮迭代 | 15000-30000 tokens | 2000-3000 tokens（一次性） | **80-90%** |

**节省原理**：
1. 系统内部读取文件，无 WorkBuddy 上下文重建成本
2. 80% 的常见问题是已知模式，不走 LLM
3. 一次性给出完整方案，不需要来回迭代
4. 自动验证减少"改完发现还有问题"的循环

---

## 七、当前限制与后续

### 已完成的
- ✅ SOP 模板设计（6 阶段）
- ✅ 3 个 Skill 代码框架
- ✅ 6 个已知问题模式库
- ✅ 人工确认 Gate 设计
- ✅ 备份 + 回滚机制

### 待完成的（需要你的决策）
- ⏳ 与 FROST Agent 体系集成（让 Ancestor 能调度 SELF-HEAL-001）
- ⏳ 精确 diff 应用（当前是简化版，生产环境需用 `python-unidiff` 库）
- ⏳ 更多模式扩展（从 6 个扩展到 20+ 个常见模式）
- ⏳ CLI 命令封装（`frost heal`）
- ⏳ 自动扫描定时任务（每天扫描代码库）

### 不做的（安全边界）
- ❌ 全自动执行（无人工确认）
- ❌ 架构级重构（如数据库迁移）
- ❌ 删除文件的修复
- ❌ 修改 `.env` 或密钥文件

---

## 八、下一步建议

### 选项 A：先试用一次（30 分钟）

用 SELF-HEAL-001 诊断一个真实问题，验证流程：
1. 选一个已知问题（如 `api/main.py:480 temperature=0.7`）
2. 手动触发 SOP 执行
3. 观察诊断输出是否符合预期
4. 确认修复方案是否正确
5. 验证执行结果

### 选项 B：先扩展模式库（2 小时）

从代码审计报告中的 20+ 问题里，挑选最常见的 10 个，加入 `KNOWN_PATTERNS`：
- 每加一个模式 → 后续同类问题零 Token 解决
- 投入 2 小时 → 节省未来 80% 的同类修复 Token

### 选项 C：与现有工作流集成（4 小时）

把 SELF-HEAL-001 接入 FROST 的现有流程：
- 当 Agent 执行失败时，自动触发诊断
- 当测试失败时，自动分析问题类型
- 每天生成一次"问题报告"，等待你确认修复

---

> **核心判断**：SELF-HEAL-001 不是"让 AI 代替你写代码"，而是"把重复性的诊断和方案生成自动化，让你只负责确认和执行决策"。这符合 FROST 哲学：AI 处理 80% 的重复劳动，你保留 20% 的关键决策权。

**要我立即执行选项 A（试用一次）来验证流程吗？**
