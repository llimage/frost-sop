# FROST-SOP 与白皮书对齐校准报告（修正版 V8.0）

**版本**: V7.4 → V8.0 校准  
**日期**: 2026-07-18  
**修正**: 家族 ≠ 个人，愿景 = 使用者业务需求（非系统内部目标）

---

## 0. 关键修正：家族与个人的区分

### 之前的错误
将 FROST-SOP 视为"从零成长的个人"，批判9件预置武器违背"能力涌现"哲学。

### 正确的理解
**FROST-SOP 是一个家族，不是一个人。**

| | 个人 | 家族（FROST-SOP） |
|---|---|---|
| 起点 | 空白 | 已有基因/宪法 |
| 能力来源 | 随用随长 | 核心自带 + 外延涌现 |
| 扩张方式 | 学习 | 繁殖（狩猎/进化/spawn） |

**家族成立时已有基因**：当前9件武器 = 家族基因，不是"配置清单"，是 DNA。
- `call_llm` = 家族的大脑
- `plan_generator` = 家族的祖辈本能
- `ceo_assessment` = 家族的免疫系统
- `lesson_archivist` = 家族的记忆基因

这些预设不是 bug，是 feature。**家族不需要从零开始。**

真正需要涌现的，是 **OPC 使用 FROST-SOP 后在业务实践中发现的能力**——这才是"外延能力"。

---

## 1. 已对齐的部分（修正后）

### 1.1 家族基因 = 预设核心能力 ✅

白皮书（个人视角）："反对预先定义技能清单"

FROST-SOP（家族视角）：**家族基因不是"技能清单"，是 DNA。**

就像一个人出生时已有DNA，不是后天学习的。但这个人后天学会的技能才是涌现的。

当前9件 `is_preset=True` 的武器 = 家族DNA，无需删除或动态加载。

**对齐度**: 完全对齐。白皮书描述的是"个人成长"，FROST-SOP 是"家族运营"，两者不在同一层。

### 1.2 愿景 = 使用者业务需求（修正）✅/🟡

**之前的理解（错误）**: 愿景是系统内部的长期目标，需要新增 `Vision` 实体。

**正确的理解**: 愿景是**朝廷（使用者）的业务需求**，但使用者往往说不清楚。

```
使用者说: "我要做轻量化心理健康服务"
          ↓
    这是模糊的需求，不是愿景
          ↓
祖辈（LLM）通过对话逐步澄清:
    - "你现在的收入来源是什么？"
    - "你的核心技能是什么？"
    - "你的目标用户是谁？"
          ↓
逐步对齐后，形成"愿景":
    "为25-35岁一线城市职场女性提供轻量级
     在线心理支持服务，月度预算1000元，
     3个月内获得第一笔收入"
          ↓
愿景对齐完成 → 进入缺口识别 → 计划生成
```

**当前实现**: 
- `SOP-INTAKE-001`（5个战略问题）= 愿景对齐的第一步
- 但只有一次性的"审问"，没有**持续的对话对齐**

**对齐度**: 部分对齐。有缺口识别，但缺少"持续对齐"机制。

### 1.3 能力涌现机制 ✅

白皮书："能力是动态涌现，而非一次性赋值"

当前实现：
- `WeaponLifecycle` 管理完整流转
- `evolve()` 支持自我进化
- `consecutive_failures` 追踪失败触发进化
- `HunterAgent` 设计支持外部发现

**对齐度**: 高。但涌现应该主要发生在**业务层武器**，而非家族基因。

### 1.4 知识整合与复盘 ✅/🟡

白皮书："知识资产的清洗—关联—激活"

当前实现：
- `lesson_archivist` = 原始信息录入 ✅
- 缺少：置信度标注、交叉验证、知识关联 🟡

**对齐度**: 中。有录入，但清洗和关联不完整。

---

## 2. 修正后的差距分析

### 2.1 🟡 愿景对齐：从"一次性审问"到"持续对话"

**当前**: `SOP-INTAKE-001` 是一次性的5个问题，回答完就进入计划生成。

**问题**: 使用者在实践中会发现新的需求、修正之前的想法。一次性的审问无法捕捉这种变化。

**白皮书对应**: "愿景为整个循环提供方向，而非一次性填写"

**需要的机制**:

```
┌─────────────────────────────────────────────────┐
│           愿景对齐对话（持续进行）                │
├─────────────────────────────────────────────────┤
│  朝廷（使用者）        ←→        家族（系统）    │
│     │                              │            │
│     │ "我想做心理健康服务"          │            │
│     │────────────────────────────→│            │
│     │                              │            │
│     │         "你的目标用户是谁？"   │            │
│     │←────────────────────────────│            │
│     │                              │            │
│     │ "25-35岁职场女性"             │            │
│     │────────────────────────────→│            │
│     │                              │            │
│     │         "你的月度预算？"       │            │
│     │←────────────────────────────│            │
│     │                              │            │
│     │  ... 多轮对话 ...              │            │
│     │                              │            │
│     │         "基于我们的对话，       │            │
│     │          你的愿景已更新为..."  │            │
│     │←────────────────────────────│            │
│     │                              │            │
│     │ [执行计划]                     │            │
│     │────────────────────────────→│            │
│     │                              │            │
│     │         "执行中发现你的用户     │            │
│     │          实际是大学生，        │            │
│     │          是否修正愿景？"       │            │
│     │←────────────────────────────│            │
│     │                              │            │
│     │ "是的，修正目标用户为大学生"    │            │
│     │────────────────────────────→│            │
│     │                              │            │
│     │ [愿景更新 → 计划重新生成]       │            │
│     │                              │            │
└─────────────────────────────────────────────────┘
```

**这不是一个 Skill，这是一个对话协议。**

### 2.2 🟡 能力成熟度标记

白皮书：🔴 初创 → 🟡 测试 → 🟢 稳定

当前系统：`WeaponState`（生命周期状态）≠ 成熟度

**需要的**: 在 `WeaponMetadata` 中新增 `maturity_level` 字段，用于业务层武器。

### 2.3 🟡 知识清洗

当前有录入，缺少清洗。需要 `skill:knowledge_curator`。

### 2.4 🟡 系统化复盘

缺少日/周/月的定时复盘机制。

---

## 3. 优先级（修正后）

| 优先级 | 差距 | 原因 | 工作量 |
|--------|------|------|--------|
| **P0** | 愿景对齐对话机制 | 当前是一次性审问，需要持续对话 | 中 |
| **P1** | 能力成熟度标记 | 区分家族基因和业务武器 | 低 |
| **P1** | 知识清洗 | 原始信息未过滤 | 中 |
| **P2** | 系统化复盘 | 缺少持续改进节奏 | 中 |

**注意**: "预设清单问题"从 P0 移除——9件家族基因是正确的，不是问题。

---

## 4. V8.0 核心方向：愿景对齐协议

### 4.1 概念定义

- **朝廷**: 任务下达者（使用者）
- **家族**: FROST-SOP 系统
- **愿景**: 朝廷的业务需求，经对话逐步清晰化
- **对齐**: 家族通过多轮对话理解朝廷真实意图的过程

### 4.2 对话协议设计

```yaml
# vision-alignment-protocol.yaml
name: 愿景对齐协议
version: 1.0

protocol:
  # 协议不是一次性的，是持续进行的
  type: continuous_dialogue
  
  phases:
    - name: 初次接触
      trigger: 使用者首次表达需求
      action: 
        - 执行 SOP-INTAKE-001（5个战略问题）
        - 生成初始愿景摘要
      output: vision_v0
      
    - name: 深度对齐
      trigger: 初次接触后，或使用者提供新信息
      action:
        - 基于已有愿景，提出澄清问题
        - 识别矛盾或不一致之处
        - 更新愿景摘要
      output: vision_vN
      
    - name: 执行反馈
      trigger: 计划执行过程中
      action:
        - 监控执行结果与愿景的偏差
        - 如发现偏差，主动向使用者确认
        - "执行数据显示你的用户画像与愿景不符，是否修正？"
      output: vision_update
      
    - name: 迭代回顾
      trigger: 每周/每月
      action:
        - 总结愿景变化历史
        - 识别使用者的偏好模式
        - 预测下一步可能的愿景调整
      output: vision_evolution_report

  storage:
    # 愿景历史存储
    key_pattern: "vision:{user_id}/history"
    # 当前生效愿景
    key_pattern: "vision:{user_id}/current"
    # 对齐对话记录
    key_pattern: "vision:{user_id}/dialogue"
```

### 4.3 新增组件

**组件1: 愿景存储层**
```python
# core/vision.py
@dataclass
class Vision:
    id: str                    # vision_{user_id}_{timestamp}
    user_id: str               # 使用者标识
    version: int               # 版本号（每次对齐递增）
    raw_input: str             # 使用者的原始输入
    clarified_vision: str      # 澄清后的愿景描述
    key_assumptions: list      # 关键假设（可被验证/推翻）
    alignment_score: float     # 对齐度评分（0-100）
    dialogue_history: list     # 对话历史
    created_at: str
    updated_at: str

class VisionStore:
    def save(self, vision: Vision)
    def get_current(self, user_id: str) -> Vision
    def get_history(self, user_id: str) -> list[Vision]
    def detect_drift(self, user_id: str, execution_result: dict) -> bool
        # 检测执行结果是否与当前愿景偏离
```

**组件2: 对齐对话 Skill**
```python
# skills/strategy/vision_aligner.py

def align_vision(context: dict) -> dict:
    """
    愿景对齐 Skill。
    
    输入:
        _user_input: str - 使用者的最新输入
        _current_vision: Vision - 当前生效的愿景（如有）
        _execution_feedback: dict - 执行反馈（如有）
    
    输出:
        _vision: Vision - 更新后的愿景
        _clarification_questions: list - 需要进一步澄清的问题
        _alignment_score: float - 当前对齐度
        _needs_replanning: bool - 是否需要重新生成计划
    """
    
    # 1. 如果有执行反馈，检测偏差
    if _execution_feedback:
        drift = detect_vision_drift(_current_vision, _execution_feedback)
        if drift:
            return {
                "_vision": _current_vision,
                "_clarification_questions": [generate_drift_question(drift)],
                "_alignment_score": _current_vision.alignment_score - 10,
                "_needs_replanning": False,  # 先确认，再重规划
            }
    
    # 2. 如果是新输入，进行澄清对话
    if _user_input:
        questions = generate_clarification_questions(_user_input, _current_vision)
        updated_vision = update_vision_from_input(_current_vision, _user_input)
        return {
            "_vision": updated_vision,
            "_clarification_questions": questions,
            "_alignment_score": calculate_alignment(updated_vision),
            "_needs_replanning": has_vision_changed_significantly(_current_vision, updated_vision),
        }
```

**组件3: 愿景偏差检测**
```python
def detect_vision_drift(vision: Vision, execution_result: dict) -> dict | None:
    """
    检测执行结果是否与愿景偏离。
    
    示例:
    - 愿景: "目标用户是25-35岁职场女性"
    - 执行结果: "实际注册用户中70%为大学生"
    - 偏差: 用户画像不符
    
    返回: {"type": "user_persona_mismatch", "expected": "职场女性", "actual": "大学生"}
    """
```

### 4.4 使用流程

```
使用者: "我要做心理健康服务"
    ↓
[vision_aligner] 执行初次对齐
    - 执行 SOP-INTAKE-001
    - 生成 vision_v0
    - 对齐度: 60%（还需要更多信息）
    ↓
系统: "基于你的回答，还有一些需要澄清：
       1. 你打算通过什么渠道触达用户？
       2. 你的服务是付费还是免费？"
    ↓
使用者: "通过微信公众号，付费服务"
    ↓
[vision_aligner] 更新愿景
    - vision_v1
    - 对齐度: 80%
    ↓
[plan_generator] 基于 vision_v1 生成计划
    ↓
[footman] 执行计划
    ↓
[lesson_archivist] 记录执行结果
    ↓
[vision_aligner] 检测偏差
    - 执行数据: "注册用户中60%为男性，与愿景中的女性用户不符"
    - 对齐度下降为 65%
    ↓
系统: "执行数据显示你的实际用户中60%为男性，
       与你之前描述的'职场女性'目标有偏差。
       是否需要：
       A. 修正目标用户为不限性别
       B. 调整营销策略以吸引女性用户
       C. 保持原愿景，继续观察"
    ↓
使用者: "选A，修正目标用户"
    ↓
[vision_aligner] 更新愿景 → vision_v2
    ↓
[plan_generator] 重新生成计划
    ↓
...
```

---

## 5. 与白皮书的对齐关系

| 白皮书概念 | V8.0 实现 | 状态 |
|-----------|----------|------|
| "愿景校准" | `vision_aligner` Skill + Vision 存储 | 新增 P0 |
| "缺口识别" | `SOP-INTAKE-001` | 已对齐 ✅ |
| "定向研究" | `HunterAgent`（狩猎） | 设计中 |
| "知识整合" | `knowledge_curator`（待实现） | 部分对齐 🟡 |
| "能力涌现" | `WeaponLifecycle.evolve()` | 已对齐 ✅ |
| "回顾迭代" | 周/月复盘定时任务（待实现） | 部分对齐 🟡 |
| "家族基因" | 9件 `is_preset=True` 武器 | 正确 ✅ |
| "业务能力" | 狩猎发现的外部武器 | 待实现 🟡 |

---

## 6. 诚实声明（最终版）

**系统做对了什么**:
- 家族基因（9件武器）= 正确的设计，不应改动
- 能力生命周期管理（进化/退役）= 与白皮书对齐
- 并行执行与府兵协同 = 超出白皮书的工程实现

**系统需要补什么**:
- **愿景对齐协议**: 从一次性审问变为持续对话（P0）
- **能力成熟度标记**: 🔴🟡🟢 区分（P1）
- **知识清洗**: 置信度、交叉验证（P1）
- **系统化复盘**: 定时任务驱动（P2）

**最大的诚实**:
当前系统是一个"能执行任务的家族"，但还不是一个"能理解主人的家族"。愿景对齐协议解决的是"家族听懂朝廷在说什么"的问题——这是从"工具"到"伙伴"的跃迁。

---

## 7. 下一步

**建议**: 先实现愿景对齐协议的最小版本：

1. `core/vision.py` — Vision 实体和存储
2. `skills/strategy/vision_aligner.py` — 对齐 Skill（支持初次对齐 + 偏差检测）
3. 修改 `plan_generator` — 输入从 `_task_description` 改为 `_vision`
4. 测试: 模拟"使用者说模糊需求 → 系统澄清 → 生成计划 → 执行偏差 → 重新对齐"的完整流程

**这是最接近白皮书"愿景校准"理念的最小实现。**

---

*版本: V8.0-alignment-revised*  
*修正: 家族基因正确，愿景 = 使用者需求，对齐是持续对话*
