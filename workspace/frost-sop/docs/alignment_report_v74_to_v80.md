# FROST-SOP 与白皮书对齐校准报告

**版本**: V7.4 → V8.0 校准  
**日期**: 2026-07-18  
**原则**: 代码诚实——不掩盖差距，不假装对齐

---

## 1. 已对齐的部分

### 1.1 能力涌现机制 ✅

白皮书："能力是动态涌现，而非一次性赋值"

当前实现：
- `WeaponLifecycle` 管理武器从 `DISCOVERED → VALIDATED → TRIALED → ARCHIVED → ACTIVE → DEPRECATED → RETIRED` 的完整流转
- `WeaponMetadata.evolve()` 支持武器自我进化（版本递增、健康评分重置、历史记录）
- `evolution_history` 记录每次版本变更的触发原因和变更内容

**对齐度**: 高。系统已具备能力的生命周期管理和进化能力。

### 1.2 缺口识别与定向研究 ✅

白皮书："将模糊的'缺乏'转化为具体、可调研的问题"

当前实现：
- `SOP-INTAKE-001`（需求澄清）在计划生成前执行5个战略问题
- `skill:plan_generator` 将任务描述拆解为结构化计划（识别7个商业闭环模块）
- `skill:ceo_assessment` 评估资源/法规/竞争/退出路径，发现隐性缺口

**对齐度**: 中。有缺口识别机制，但问题列表是预设的（Q1-Q5），非动态生成。

### 1.3 知识整合与复盘 ✅

白皮书："知识资产的清洗—关联—激活"

当前实现：
- `skill:lesson_archivist` 自动记录执行教训，生成结构化复盘
- `consecutive_failures` 追踪连续失败，触发进化
- `health_score` 动态反映武器质量（成功率+使用频率+时效性）

**对齐度**: 中。有教训归档，但缺少"知识清洗"（置信度标注、交叉验证）和"知识关联"（能力图谱）的完整实现。

### 1.4 反对静态清单 ✅

白皮书："反对预先定义技能清单"

当前实现：
- `WeaponType.TACTIC`（原SOP）的命名调整，强调战术是涌现的而非预设的
- `is_preset=False` 的武器可被进化、替换、退役
- `HunterAgent` 设计文档支持从外部动态发现新能力

**对齐度**: 中。概念上对齐，但当前9件武器全部为 `is_preset=True`，实际上仍是预置清单。

---

## 2. 存在的差距

### 2.1 🔴 关键差距：愿景层缺失

白皮书核心循环以"愿景校准"为起点。当前系统没有"愿景"概念。

当前流程：
```
任务描述 → 计划生成 → 执行
```

白皮书要求：
```
愿景校准 → 缺口识别 → 定向研究 → 知识整合 → 能力涌现 → 执行验证 → 回顾迭代
```

**影响**: 府兵执行的是孤立任务，没有与长期目标对齐。

**校准方案**:
- 新增 `Vision` 实体（愿景），包含长期目标、关键里程碑、当前阶段
- 每次任务执行前，检查任务与愿景的对齐度
- 新增 `skill:vision_alignment` 评估当前计划是否支持愿景

### 2.2 🟡 能力成熟度标记缺失

白皮书：🔴 初创 → 🟡 测试 → 🟢 稳定

当前系统：`WeaponState`（生命周期状态）≠ 成熟度标记

| 白皮书 | 当前系统 |
|--------|---------|
| 🔴 初创（已有初步情报，尚未验证）| 无对应 |
| 🟡 测试（已有可执行流程，正小规模实践）| `TRIALED` 部分对应 |
| 🟢 稳定（经多次成功验证，可复用）| `ACTIVE` 部分对应 |

**影响**: 无法区分"刚入库的新武器"和"久经考验的老武器"。

**校准方案**:
- 在 `WeaponMetadata` 新增 `maturity_level` 字段：`nascent` / `testing` / `stable`
- `evolve()` 生成的武器默认 `maturity=nascent`
- 成功率>80% + 使用>10次 → 自动升级为 `stable`

### 2.3 🟡 知识清洗流程不完整

白皮书要求："去重、交叉验证、置信度标注、结构化提炼"

当前系统：
- 有 `lesson_archivist` 记录教训（原始信息录入）
- 缺少：
  - 置信度标注（高/中/低）
  - 交叉验证（多来源比对）
  - 知识关联（教训与能力的映射）
  - 结构化提炼（原始情报 → 可复用原则）

**校准方案**:
- 新增 `skill:knowledge_curator`（知识策展人）
- 教训入库后自动触发清洗流程
- 新增 `confidence` 字段到知识条目
- 支持教训与武器的双向关联

### 2.4 🟡 预设清单问题

当前 `weapon_manifest.py` 有9件 `is_preset=True` 的武器。白皮书明确反对"配置清单"。

**诚实分析**:
- 9件武器是系统启动的最小必要能力（事件总线、LLM调用、计划生成等基础设施）
- 这些不是"商业能力"，而是"系统能力"
- 类比：白皮书的"最小循环启动"也需要基础工具

**校准方案**:
- 区分"基础设施"（必须预设）和"业务能力"（必须涌现）
- 基础设施标记 `is_preset=True, category=INFRASTRUCTURE`
- 业务能力标记 `is_preset=False`，通过狩猎/进化获得
- 将 `plan_generator`、`ceo_assessment` 等业务能力改为 `is_preset=False`，通过首次使用触发动态加载

### 2.5 🟡 系统化复盘节奏缺失

白皮书要求：日记录、周复盘、月深度回顾

当前系统：
- 有 `lesson_archivist`（执行后归档）
- 缺少：
  - 每日简要记录（做了什么、关键决策）
  - 周复盘（循环检查、能力成熟度变化）
  - 月深度回顾（愿景相关性评估）

**校准方案**:
- 新增 `Cron` 定时任务：每周自动执行复盘 Skill
- 新增 `skill:weekly_retrospective` 和 `skill:monthly_review`
- 复盘结果自动生成新的研究任务或知识更新

---

## 3. 校准优先级

| 优先级 | 差距 | 影响 | 工作量 |
|--------|------|------|--------|
| P0 | 愿景层缺失 | 任务与长期目标脱节 | 中 |
| P0 | 预设清单问题 | 违背核心哲学 | 低（改配置） |
| P1 | 成熟度标记 | 无法区分新旧能力 | 低 |
| P1 | 知识清洗 | 信息噪音未过滤 | 中 |
| P2 | 系统化复盘 | 缺少持续改进节奏 | 中 |

---

## 4. 具体校准动作

### 4.1 立即执行（P0）

**动作1: 区分基础设施与业务能力**
```python
# weapon_manifest.py 中
# 基础设施（允许预设）
call_llm = WeaponMetadata(..., category=WeaponCategory.INFRASTRUCTURE, is_preset=True)

# 业务能力（不应预设）
plan_generator = WeaponMetadata(..., is_preset=False, state=WeaponState.DISCOVERED)
# 首次使用时触发动态加载（WeaponLoader 从代码模块加载）
```

**动作2: 新增愿景实体**
```python
# core/vision.py
@dataclass
class Vision:
    id: str
    description: str  # "6个月内建立可盈利的独立业务"
    milestones: list[dict]  # [{"phase": "MVP", "deadline": "..."}]
    current_gap: str  # 当前最大缺口
    alignment_score: float  # 最近一次任务的对齐度
```

### 4.2 短期执行（P1）

**动作3: 新增成熟度标记**
```python
# core/armory.py 新增
class MaturityLevel(Enum):
    NASCENT = "nascent"      # 🔴 初创
    TESTING = "testing"      # 🟡 测试
    STABLE = "stable"        # 🟢 稳定

# WeaponMetadata 新增字段
maturity_level: MaturityLevel = MaturityLevel.NASCENT
maturity_evidence: list[dict] = field(default_factory=list)  # 成熟度升级依据
```

**动作4: 新增知识策展人**
```python
# skills/strategy/knowledge_curator.py
def curate_lessons(context):
    """
    知识清洗流程：
    1. 读取未清洗的教训
    2. 交叉验证（同类型教训是否一致）
    3. 置信度标注
    4. 关联到相关武器
    5. 提炼为可复用原则
    """
```

### 4.3 中期执行（P2）

**动作5: 系统化复盘定时任务**
```python
# 每周日 21:00 自动执行周复盘
Cron.create(
    name="weekly_retrospective",
    trigger={"kind": "cron", "expr": "0 21 * * 0"},
    execution={
        "kind": "local_conversation",
        "workspacePath": "...",
        "prompt": "执行周复盘：检查本周循环运行状况、能力成熟度变化、下周重点"
    }
)
```

---

## 5. 诚实声明

**当前系统已实现的**:
- 能力的生命周期管理（进化、退役、健康评分）
- 场景驱动的自主配发（府兵不再硬编码）
- 教训归档与失败追踪
- 并行执行与府兵协同

**当前系统缺失的**:
- 愿景层（长期目标对齐）
- 能力成熟度标记（🔴🟡🟢）
- 知识清洗（置信度、交叉验证）
- 系统化复盘节奏（日/周/月）
- 真正的"零预设启动"（当前9件武器是预设的）

**最大的诚实**:
当前的9件预置武器是一个务实的起点，但不是白皮书的理想态。V8.0 的目标是让这些武器从"预设"变为"自举"——系统启动时只有3件基础设施（事件总线、LLM调用、存储），其余6件在首次使用时通过 `WeaponLoader` 动态发现加载。

---

## 6. 下一步建议

1. **选P0执行**：先解决愿景层和预设清单问题（改动小，影响大）
2. **保留当前架构**：进化、自主决策、并行编排是正确的，不需要推翻
3. **渐进校准**：不要一次性改完，每次迭代解决一个差距

**你愿意先走哪一步？** 我建议先处理 P0 的"区分基础设施与业务能力"——只需要改 `weapon_manifest.py` 的配置，将6件业务能力改为 `is_preset=False`，让系统在首次使用时动态加载。这是最接近白皮书"从零生长"理念的最小改动。
