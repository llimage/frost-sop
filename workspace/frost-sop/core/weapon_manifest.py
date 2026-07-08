"""
FROST-SOP V7.4 — 武器清单（Weapon Manifest）

所有武器的统一注册中心。
PHILOSOPHY: 武器不是代码，武器是元数据驱动的能力单元。

注册原则：
1. 每个武器必须有明确的适用场景（applicable_scenarios）
2. 每个武器必须有武器类型（SKILL/SOP/INTEL/IMMUN/BIND/GENE）
3. 每个武器必须有功能域（COGNITIVE/EXECUTION/GOVERNANCE/STRATEGY/IMMUNE/ORCHESTRATE/SEARCH/COMMUNICATION）
4. 预置武器（is_preset=True）不可删除

新增武器时，只需在此文件添加 WeaponMetadata 定义即可。
"""

from core.armory import WeaponMetadata, WeaponType, WeaponCategory, WeaponState

# ────────────────────────────────────────────────────────────────────────────
# 战略层武器（祖辈/父辈）
# ────────────────────────────────────────────────────────────────────────────

PLAN_GENERATOR = WeaponMetadata(
    id="skill:plan_generator",
    name="计划生成器",
    type=WeaponType.SKILL,
    category=WeaponCategory.STRATEGY,
    description="祖辈核心武器：将需求拆解为结构化计划（含商业闭环7模块）",
    applicable_scenarios=["需求拆解", "战略计划", "商业闭环分析", "一人公司规划"],
    not_applicable_scenarios=["代码编写", "数据清洗"],
    tags=["grandparent", "planning", "strategy", "business-closure"],
    state=WeaponState.ACTIVE,
    is_active=True,
    is_preset=True,
    created_from="manual",
    source="skills/strategy/plan_generator.py",
)

PLAN_REFINER = WeaponMetadata(
    id="skill:plan_refiner",
    name="计划细化器",
    type=WeaponType.SKILL,
    category=WeaponCategory.STRATEGY,
    description="父辈核心武器：将祖辈战略计划细化为可执行计划，识别并行机会",
    applicable_scenarios=["计划细化", "并行识别", "战术规划", "任务分解"],
    not_applicable_scenarios=["代码执行", "文件操作"],
    tags=["parent", "planning", "parallel", "refinement"],
    state=WeaponState.ACTIVE,
    is_active=True,
    is_preset=True,
    created_from="manual",
    source="agents/parent.py",
)

PARALLEL_ORCHESTRATOR = WeaponMetadata(
    id="skill:parallel_orchestrator",
    name="并行编排器",
    type=WeaponType.SKILL,
    category=WeaponCategory.ORCHESTRATE,
    description="解析 parallel_group 并调度并行执行，管理组间依赖和数据流",
    applicable_scenarios=["并行执行", "组调度", "协同编排", "多Agent协调"],
    not_applicable_scenarios=["单任务执行", "顺序执行"],
    tags=["parallel", "orchestrate", "coordinator", "dependency-graph"],
    state=WeaponState.ACTIVE,
    is_active=True,
    is_preset=True,
    created_from="manual",
    source="agents/parent.py",
)

# ────────────────────────────────────────────────────────────────────────────
# 治理层武器（审计/评估/合规）
# ────────────────────────────────────────────────────────────────────────────

CEO_ASSESSMENT = WeaponMetadata(
    id="skill:ceo_assessment",
    name="CEO评估器",
    type=WeaponType.SKILL,
    category=WeaponCategory.GOVERNANCE,
    description="执行前评估：资源/法规/竞争/退出路径四维度评分，GO/NO-GO决策",
    applicable_scenarios=["风险评估", "可行性分析", "GO/NO-GO决策", "创业前评估"],
    not_applicable_scenarios=["代码审查", "UI设计"],
    tags=["assessment", "risk", "governance", "ceo", "feasibility"],
    state=WeaponState.ACTIVE,
    is_active=True,
    is_preset=True,
    created_from="manual",
    source="skills/strategy/ceo_assessment.py",
)

AUDITOR = WeaponMetadata(
    id="skill:auditor",
    name="审计器",
    type=WeaponType.SKILL,
    category=WeaponCategory.GOVERNANCE,
    description="Devil's Advocate：检查计划漏洞（逻辑矛盾/资源冲突/风险遗漏/假设错误）",
    applicable_scenarios=["计划审计", "漏洞检查", "质量把关", "计划评审"],
    not_applicable_scenarios=["创意生成", "市场调研"],
    tags=["audit", "quality", "governance", "devils-advocate", "review"],
    state=WeaponState.ACTIVE,
    is_active=True,
    is_preset=True,
    created_from="manual",
    source="agents/auditor.py",
)

# ────────────────────────────────────────────────────────────────────────────
# 学习层武器（知识管理）
# ────────────────────────────────────────────────────────────────────────────

LESSON_ARCHIVIST = WeaponMetadata(
    id="skill:lesson_archivist",
    name="教训归档器",
    type=WeaponType.SKILL,
    category=WeaponCategory.COMMUNICATION,
    description="自动记录执行教训，生成结构化复盘，防止重复失败",
    applicable_scenarios=["复盘", "知识管理", "持续改进", "失败分析"],
    not_applicable_scenarios=["计划制定", "任务执行"],
    tags=["lesson", "archive", "learning", "retrospective", "knowledge"],
    state=WeaponState.ACTIVE,
    is_active=True,
    is_preset=True,
    created_from="manual",
    source="skills/strategy/lesson_archivist.py",
)

# ────────────────────────────────────────────────────────────────────────────
# 需求层武器（SOP）
# ────────────────────────────────────────────────────────────────────────────

INTAKE_CLARIFIER = WeaponMetadata(
    id="tactic:SOP-INTAKE-001",
    name="需求澄清TACTIC",
    type=WeaponType.TACTIC,
    category=WeaponCategory.GOVERNANCE,
    description="计划生成前审问：5个战略问题防止模糊需求",
    applicable_scenarios=["需求澄清", "项目启动", "客户沟通", "战略对齐"],
    not_applicable_scenarios=["技术实现", "代码编写"],
    tags=["intake", "requirements", "clarification", "tactic"],
    state=WeaponState.ACTIVE,
    is_active=True,
    is_preset=True,
    created_from="manual",
    source="sops/SOP-INTAKE-001.yaml",
)

PARENT_WORKFLOW = WeaponMetadata(
    id="tactic:SOP-PARENT-001",
    name="父辈工作流程TACTIC",
    type=WeaponType.TACTIC,
    category=WeaponCategory.STRATEGY,
    description="父辈战术细化的标准操作流程：接收→拆解→并行识别→依赖解析→输出",
    applicable_scenarios=["战术规划", "计划细化", "并行设计"],
    not_applicable_scenarios=["战略制定", "代码执行"],
    tags=["parent", "workflow", "tactic", "refinement"],
    state=WeaponState.ACTIVE,
    is_active=True,
    is_preset=True,
    created_from="manual",
    source="sops/SOP-PARENT-001.yaml",
)


# ────────────────────────────────────────────────────────────────────────────
# 认知层武器（基础能力）
# ────────────────────────────────────────────────────────────────────────────

CALL_LLM = WeaponMetadata(
    id="skill:call_llm",
    name="LLM调用器",
    type=WeaponType.SKILL,
    category=WeaponCategory.COGNITIVE,
    description="基础认知能力：调用大语言模型完成推理、生成、分析",
    applicable_scenarios=["文本生成", "推理分析", "对话", "代码生成"],
    tags=["llm", "cognitive", "foundation", "core"],
    state=WeaponState.ACTIVE,
    is_active=True,
    is_preset=True,
    created_from="manual",
    source="skills/llm.py",
)


# ────────────────────────────────────────────────────────────────────────────
# V8.0 新增武器：项目生命周期
# ────────────────────────────────────────────────────────────────────────────

VISION_ALIGNER = WeaponMetadata(
    id="skill:vision_aligner",
    name="愿景对齐器",
    type=WeaponType.SKILL,
    category=WeaponCategory.STRATEGY,
    description="V8.0：与朝廷持续对话，将模糊需求逐步对齐为清晰愿景",
    applicable_scenarios=["项目启动", "愿景对齐", "需求澄清", "偏差检测", "愿景更新"],
    not_applicable_scenarios=["代码编写", "数据清洗"],
    tags=["vision", "alignment", "dialogue", "parent", "project"],
    state=WeaponState.ACTIVE,
    is_active=True,
    is_preset=True,
    created_from="manual",
    source="skills/strategy/vision_aligner.py",
)

PROJECT_EXECUTOR = WeaponMetadata(
    id="skill:project_executor",
    name="项目执行器",
    type=WeaponType.SKILL,
    category=WeaponCategory.ORCHESTRATE,
    description="V8.0：组建府兵小队、调度并行执行、监控进度、汇总结果",
    applicable_scenarios=["计划执行", "府兵调度", "并行编排", "进度监控", "结果汇总"],
    not_applicable_scenarios=["愿景对齐", "需求澄清"],
    tags=["execution", "footman", "parallel", "orchestrate", "project"],
    state=WeaponState.ACTIVE,
    is_active=True,
    is_preset=True,
    created_from="manual",
    source="skills/strategy/project_executor.py",
)

MATURITY_TRACKER = WeaponMetadata(
    id="skill:maturity_tracker",
    name="成熟度追踪器",
    type=WeaponType.SKILL,
    category=WeaponCategory.GOVERNANCE,
    description="V8.0：武器成熟度评估（🔴初创→🟡测试→🟢稳定），自动升级/退化",
    applicable_scenarios=["武器评估", "健康检查", "进化触发", "成熟度标记"],
    not_applicable_scenarios=["任务执行", "计划生成"],
    tags=["maturity", "health", "evolution", "assessment", "governance"],
    state=WeaponState.ACTIVE,
    is_active=True,
    is_preset=True,
    created_from="manual",
    source="skills/strategy/maturity_tracker.py",
)

PROJECT_LIFECYCLE = WeaponMetadata(
    id="tactic:project_lifecycle",
    name="项目生命周期TACTIC",
    type=WeaponType.TACTIC,
    category=WeaponCategory.STRATEGY,
    description="V8.0：项目管理全流程SOP——创建→对齐→计划→执行→复盘→归档",
    applicable_scenarios=["项目管理", "任务生命周期", "全流程管理"],
    not_applicable_scenarios=["单一技能执行", "无状态操作"],
    tags=["project", "lifecycle", "tactic", "workflow", "sop"],
    state=WeaponState.ACTIVE,
    is_active=True,
    is_preset=True,
    created_from="manual",
    source="sops/TACTIC-PROJECT-LIFECYCLE.yaml",
)
# ────────────────────────────────────────────────────────────────────────────
# 武器清单汇总
# ────────────────────────────────────────────────────────────────────────────

ALL_WEAPONS: list[WeaponMetadata] = [
    # 战略层
    PLAN_GENERATOR,
    PLAN_REFINER,
    PARALLEL_ORCHESTRATOR,
    # 治理层
    CEO_ASSESSMENT,
    AUDITOR,
    # 学习层
    LESSON_ARCHIVIST,
    # 需求层
    INTAKE_CLARIFIER,
    PARENT_WORKFLOW,
    # 认知层
    CALL_LLM,
    # V8.0 新增
    VISION_ALIGNER,
    PROJECT_EXECUTOR,
    MATURITY_TRACKER,
    PROJECT_LIFECYCLE,
]


def register_all_weapons(registry) -> int:
    """
    将所有武器注册到武器库。

    Args:
        registry: ArmoryRegistry 实例

    Returns:
        成功注册数量
    """
    count = 0
    for weapon in ALL_WEAPONS:
        if registry.register(weapon):
            count += 1
    return count


def get_weapon_manifest() -> dict:
    """
    获取武器清单摘要。

    Returns:
        按类别分组的武器清单
    """
    manifest = {}
    for weapon in ALL_WEAPONS:
        cat = weapon.category.value
        if cat not in manifest:
            manifest[cat] = []
        manifest[cat].append({
            "id": weapon.id,
            "name": weapon.name,
            "type": weapon.type.value,
            "scenarios": weapon.applicable_scenarios,
            "tags": weapon.tags,
        })
    return manifest
