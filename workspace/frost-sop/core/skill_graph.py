"""
FROST-SOP V4.0 预研 - 技能图数据模型定义
PHILOSOPHY: 技能图是家族能力网络的拓扑表示。
SkillNode 是能力节点，SkillEdge 是能力间的依赖与编排关系。
SkillCard 是人类可读的能力说明书，PlatformBinding 绑定具体平台工具调用。

Phase 1: 纯数据结构定义，不修改任何现有代码。
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional, Any


class EdgeType(Enum):
    """技能边类型枚举"""
    SEQUENCE = "sequence"          # 顺序执行：A完成后B才能开始
    PARALLEL = "parallel"          # 并行执行：A和B可同时执行
    CONDITIONAL = "conditional"    # 条件分支：满足condition时A→B
    SPECIALIZATION = "specialization"  # 特化关系：A是B的特化版本
    ALTERNATIVE = "alternative"    # 替代关系：A不可用时用B
    MUTEX = "mutex"                # 互斥关系：A和B不能同时使用
    COMPOSITION = "composition"    # 组合关系：A是B的组成部分


@dataclass
class ParamSpec:
    """参数规格"""
    name: str
    type: str                        # "string" | "int" | "float" | "bool" | "list" | "dict"
    required: bool = True
    description: str = ""
    example: Optional[str] = None


@dataclass
class ToolCall:
    """工具调用"""
    tool_name: str
    parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PlatformBinding:
    """平台绑定"""
    platform: str                    # "deepseek" | "openai" | "local_gguf" | "web_search" | ...
    tool_calls: List[ToolCall] = field(default_factory=list)
    prompt_template: str = ""
    input_mapping: Dict[str, str] = field(default_factory=dict)
    output_mapping: Dict[str, str] = field(default_factory=dict)
    known_limitations: List[str] = field(default_factory=list)
    workaround: str = ""


@dataclass
class SkillCard:
    """技能卡 - 人类可读的能力说明书"""
    intent: str                      # 这个技能想做什么
    applicable_when: str             # 什么场景下适用
    not_applicable_when: str = ""    # 什么场景下不适用
    inputs: List[ParamSpec] = field(default_factory=list)
    outputs: List[ParamSpec] = field(default_factory=list)
    preconditions: List[str] = field(default_factory=list)
    postconditions: List[str] = field(default_factory=list)
    completion_criteria: List[str] = field(default_factory=list)
    failure_signals: List[str] = field(default_factory=list)
    requires_capabilities: List[str] = field(default_factory=list)
    bindings: List[PlatformBinding] = field(default_factory=list)


@dataclass
class SkillNode:
    """技能节点 - 技能图中的节点"""
    id: str                          # 唯一标识
    name: str                        # 技能名称
    intent: str                      # 意图描述
    category: str = "general"        # "functional" | "governance" | "meta" | ...
    card: Optional[SkillCard] = None
    preconditions: List[str] = field(default_factory=list)
    required_skills: List[str] = field(default_factory=list)  # 前置技能ID列表
    inputs: List[ParamSpec] = field(default_factory=list)
    outputs: List[ParamSpec] = field(default_factory=list)
    completion_criteria: List[str] = field(default_factory=list)
    success_indicators: List[str] = field(default_factory=list)
    failure_modes: List[str] = field(default_factory=list)
    fallback_skill: Optional[str] = None    # 失败时的回退技能ID
    version: str = "1.0"
    created_from: str = "manual"     # "manual" | "extracted" | "synthesized"
    confidence: float = 1.0          # 置信度 0.0-1.0
    usage_count: int = 0             # 使用次数
    avg_execution_time: Optional[float] = None  # 平均执行时间(秒)


@dataclass
class SkillEdge:
    """技能边 - 技能图中节点间的关系"""
    source: str                      # 源节点ID
    target: str                      # 目标节点ID
    edge_type: EdgeType = EdgeType.SEQUENCE
    condition: str = ""              # 条件表达式（CONDITIONAL类型时使用）
    weight: float = 1.0              # 权重（用于路径选择）
    evidence: str = ""               # 关系证据/来源说明
